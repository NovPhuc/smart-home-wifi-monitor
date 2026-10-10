const POLL_MS = 2000;
const DEMO_ROOM_NAMES = {Bedroom:'Phòng ngủ',Corridor:'Hành lang',Bathroom:'Phòng tắm',LivingRoom:'Phòng khách',Kitchen:'Nhà bếp'};
const ACTIVITY = {
  CALIBRATING:['Đang hiệu chuẩn','Cần vài mẫu tín hiệu đầu tiên','CAL'],
  STILL:['Đang nghỉ ngơi','Không ghi nhận biến động đáng kể','YÊN'],
  LIGHT_ACTIVITY:['Hoạt động nhẹ','Tín hiệu thay đổi nhẹ trong phòng','NHẸ'],
  MOVING:['Đang di chuyển','Phát hiện biến động tín hiệu Wi-Fi','ĐI'],
  ROOM_CHANGE:['Vừa chuyển phòng','Đã xác nhận thay đổi vị trí','ĐỔI']
};

const state = {authenticated:false, me:null, rooms:[], devices:[], calibration:null, demoMode:false};
// Cache the last rendered payloads so the 2s poll only touches the DOM when
// something actually changed, instead of rebuilding every list each tick.
let lastRenderKey = {status:'', history:'', alerts:''};
let demoTimer = null;
let pollTimer = null;
let trainingTimer = null;
let sensorActive = false;
let lastSensorSentAt = 0;
const $ = id => document.getElementById(id);
const deviceId = localStorage.getItem('an-tam-device-id') || `phone-${crypto.randomUUID?.() || Date.now()}`;
localStorage.setItem('an-tam-device-id', deviceId);

const escapeHTML = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const roomLabel = name => DEMO_ROOM_NAMES[name] || name || 'Chưa xác định';
const fmtTime = ts => ts ? new Date(ts*1000).toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit'}) : '—';
function fmtDuration(minutes){if(minutes==null)return '—';if(minutes<1)return `${Math.round(minutes*60)} giây`;if(minutes<60)return `${minutes.toFixed(1)} phút`;return `${Math.floor(minutes/60)}g ${Math.round(minutes%60)}p`}

async function api(url, options={}) {
  const requestOptions = {...options, headers:{...(options.headers||{})}};
  if (options.body && !requestOptions.headers['Content-Type']) requestOptions.headers['Content-Type']='application/json';
  const response = await fetch(url, requestOptions);
  const data = await response.json().catch(()=>({}));
  if (!response.ok) {
    const error = new Error(data.error || `${response.status} ${response.statusText}`);
    error.status=response.status; error.data=data; throw error;
  }
  return data;
}

function setButtonBusy(button, busy, busyText='Đang xử lý…') {
  if (!button.dataset.label) button.dataset.label=button.textContent;
  button.disabled=busy;
  button.textContent=busy?busyText:button.dataset.label;
}

function showAuth(register=false) {
  state.authenticated=false;
  $('authView').hidden=false; $('appShell').hidden=true;
  selectAuthTab(register?'register':'login');
  if (pollTimer) clearInterval(pollTimer);
}

function selectAuthTab(name) {
  const register=name==='register';
  $('loginTab').setAttribute('aria-selected',String(!register));
  $('registerTab').setAttribute('aria-selected',String(register));
  $('loginForm').hidden=register; $('registerForm').hidden=!register;
  $('authError').hidden=true;
}

function clearFieldErrors(form) {
  form.querySelectorAll('.field-error').forEach(el=>el.textContent='');
  form.querySelectorAll('[aria-invalid="true"]').forEach(el=>el.removeAttribute('aria-invalid'));
}

function showAuthErrors(form, message, fields={}) {
  clearFieldErrors(form);
  $('authError').textContent=message; $('authError').hidden=false; $('authError').focus();
  const idMap={display_name:'displayName',email:form.id==='loginForm'?'loginEmail':'registerEmail',password:form.id==='loginForm'?'loginPassword':'registerPassword',home_name:'firstHomeName'};
  Object.entries(fields).forEach(([field,text])=>{const input=$(idMap[field]);const target=$(`${idMap[field]}Error`);if(input){input.setAttribute('aria-invalid','true');if(target)target.textContent=text;}});
}

async function submitAuth(form, endpoint) {
  clearFieldErrors(form); $('authError').hidden=true;
  if (!form.reportValidity()) return;
  const button=form.querySelector('button[type="submit"]'); setButtonBusy(button,true);
  const payload=Object.fromEntries(new FormData(form).entries());
  try { await api(endpoint,{method:'POST',body:JSON.stringify(payload)}); form.reset(); await loadApplication(); }
  catch(error){showAuthErrors(form,error.data?.error==='INVALID_CREDENTIALS'?'Email hoặc mật khẩu không đúng':'Vui lòng kiểm tra thông tin.',error.data?.fields||{});}
  finally {setButtonBusy(button,false);}
}

async function loadApplication() {
  try { state.me=await api('/api/auth/me'); }
  catch(error){if(error.status===401){showAuth(false);return}throw error;}
  state.authenticated=true; $('authView').hidden=true; $('appShell').hidden=false;
  $('accountName').textContent=state.me.user.display_name; $('accountEmail').textContent=state.me.user.email;
  renderHomes(); await loadHome();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer=setInterval(refreshDashboard,POLL_MS);
}

function renderHomes() {
  $('homeSelect').innerHTML=state.me.homes.map(home=>`<option value="${home.id}" ${state.me.active_home?.id===home.id?'selected':''}>${escapeHTML(home.name)}</option>`).join('');
  $('homeTitle').textContent=state.me.active_home?.name||'An Tâm Home';
}

async function loadHome() {
  const [rooms,devices,calibration]=await Promise.all([api('/api/rooms'),api('/api/devices'),api('/api/calibration')]);
  state.rooms=rooms; state.devices=devices; state.calibration=calibration; state.demoMode=false;
  lastRenderKey = {status:'', history:'', alerts:''};
  document.body.classList.remove('demo-mode');
  renderRooms(); renderDevices(); renderCalibration(calibration);
  await Promise.all([refreshDashboard(),api('/api/metrics').then(renderMetrics)]);
  checkTrainingStatus();
}

function renderRooms() {
  $('roomList').innerHTML=state.rooms.map(room=>`<div class="entity-row"><div><strong>${escapeHTML(room.name)}</strong><small>Cảnh báo lưu trú sau ${room.max_dwell_minutes} phút</small></div><button type="button" data-delete-room="${room.id}" aria-label="Xóa phòng ${escapeHTML(room.name)}">Xóa</button></div>`).join('')||'<div class="empty-state">Chưa có phòng. Hãy thêm ít nhất hai phòng.</div>';
  $('roomGrid').innerHTML=state.rooms.map(room=>`<div class="room-tile" data-room="${escapeHTML(room.name)}"><span>${escapeHTML(room.name)}</span><small>Đang chờ định vị</small></div>`).join('')||'<div class="empty-state">Chưa thiết lập phòng.</div>';
  document.querySelectorAll('[data-delete-room]').forEach(button=>button.addEventListener('click',()=>deleteRoom(Number(button.dataset.deleteRoom))));
}

function renderDevices() {
  $('deviceList').innerHTML=state.devices.map(device=>`<div class="entity-row"><div><strong>${escapeHTML(device.name)}</strong><small>${escapeHTML(device.platform)} • mã …${escapeHTML(device.token_hint)}${device.last_seen_at?` • dùng lúc ${fmtTime(device.last_seen_at)}`:''}</small></div><button type="button" data-revoke-device="${device.id}" aria-label="Thu hồi thiết bị ${escapeHTML(device.name)}">Thu hồi</button></div>`).join('')||'<div class="empty-state">Chưa có điện thoại được ghép.</div>';
  document.querySelectorAll('[data-revoke-device]').forEach(button=>button.addEventListener('click',()=>revokeDevice(Number(button.dataset.revokeDevice))));
}

function renderCalibration(calibration) {
  state.calibration=calibration;
  const roomStep=state.rooms.length>=2, deviceStep=state.devices.length>0;
  $('stepRooms').classList.toggle('complete',roomStep); $('stepDevice').classList.toggle('complete',deviceStep);
  $('stepCollect').classList.toggle('complete',calibration.data_ready); $('stepTrain').classList.toggle('complete',calibration.localization_ready);
  $('calibrationRooms').innerHTML=calibration.rooms.map(room=>{const pct=Math.min(100,room.samples/room.target_samples*100);return `<div class="calibration-room ${room.ready?'ready':''}"><header><strong>${escapeHTML(room.name)}</strong><span>${room.ready?'Đạt':'Đang thu'}</span></header><div class="progress-track" role="progressbar" aria-label="Tiến độ phòng ${escapeHTML(room.name)}" aria-valuemin="0" aria-valuemax="${room.target_samples}" aria-valuenow="${room.samples}"><i style="width:${pct}%"></i></div><small>${room.samples}/${room.target_samples} mẫu • ${room.orientations}/${room.required_orientations} hướng • ${room.sessions}/${room.required_sessions} phiên</small></div>`}).join('')||'<div class="empty-state">Thêm phòng để bắt đầu thu dữ liệu.</div>';
  const ready=calibration.localization_ready;
  document.body.classList.toggle('calibration-required',!ready&&!state.demoMode);
  $('setupStatus').textContent=ready?'SẴN SÀNG':calibration.model_status==='TRAINING'?'ĐANG HUẤN LUYỆN':'CHƯA SẴN SÀNG';
  $('setupStatus').className=`badge ${ready?'normal':calibration.model_status==='TRAINING'?'warning':'neutral'}`;
  const trainable=calibration.data_ready&&calibration.model_status!=='TRAINING';
  $('trainButton').disabled=!trainable;
  $('trainButton').textContent=calibration.model_status==='READY'?'Huấn luyện lại model':'Huấn luyện model căn nhà';
  $('trainingTitle').textContent=ready?'Model căn nhà đã sẵn sàng':calibration.data_ready?'Đã đủ dữ liệu để huấn luyện':'Chưa đủ dữ liệu huấn luyện';
  $('trainingMeta').textContent=ready?'Định vị thời gian thực đã được mở.':calibration.data_ready?'Bấm huấn luyện và giữ máy chủ hoạt động.':'Mỗi phòng cần đủ mẫu, hướng cầm và 3 phiên.';
}

async function deleteRoom(id){if(!confirm('Xóa phòng sẽ xóa toàn bộ scan đã thu của phòng này. Tiếp tục?'))return;await api(`/api/rooms/${id}`,{method:'DELETE'});await loadHome();}
async function revokeDevice(id){if(!confirm('Thu hồi mã ghép nối của thiết bị này?'))return;await api(`/api/devices/${id}`,{method:'DELETE'});state.devices=await api('/api/devices');renderDevices();renderCalibration(state.calibration);}

function setConnection(ok,timestamp){const stale=timestamp&&Date.now()/1000-timestamp>15;$('statusDot').className=ok&&!stale?'live':'error';$('statusText').textContent=!ok?'Mất kết nối':stale?'Dữ liệu đã cũ':'Hệ thống trực tuyến'}
function translateReason(reason){return String(reason||'').replace('High trajectory reconstruction error','Quỹ đạo di chuyển có sai số tái tạo cao').replace(/^Long dwell in ([^:]+):/,'Ở $1 quá lâu:').replace(/^No detected movement for/,'Không phát hiện vận động trong').replace('Possible impact followed by low motion; caregiver review required','Ghi nhận va chạm rồi ít vận động; cần kiểm tra');}

function renderStatus(status) {
  const roomName=roomLabel(status.room); $('room').textContent=status.room?roomName:'Chưa có dữ liệu';
  $('roomMeta').textContent=status.room?`${status.demo?'Demo mẫu':'Model căn nhà'} • định vị mức phòng`:'Đang chờ fingerprint Wi-Fi…';
  $('confidence').textContent=status.confidence!=null?`TIN CẬY ${(status.confidence*100).toFixed(0)}%`:'—';
  $('dwell').textContent=fmtDuration(status.dwell_minutes);$('score').textContent=status.anomaly_score!=null?status.anomaly_score.toFixed(3):'—';
  const ratio=status.anomaly_score!=null&&status.anomaly_threshold?Math.min(100,status.anomaly_score/status.anomaly_threshold*100):0;$('meterFill').style.width=`${ratio}%`;
  const activity=status.activity||{},copy=ACTIVITY[activity.state]||ACTIVITY.CALIBRATING;$('activityState').textContent=copy[0];$('activityMeta').textContent=copy[1];$('activityIcon').textContent=copy[2];$('transitions').textContent=activity.transitions_last_hour??'—';
  const value=(status.status||'NO_DATA').toUpperCase();$('safetyCard').className=`card safety-card ${value.toLowerCase()}`;$('systemBadge').className=`badge ${value==='NO_DATA'?'neutral':value.toLowerCase()}`;$('systemBadge').textContent={NORMAL:'AN TOÀN',WARNING:'CẦN CHÚ Ý',CRITICAL:'KHẨN CẤP',NO_DATA:'CHƯA CÓ DỮ LIỆU',COLLECTING:'ĐANG GOM MẪU'}[value]||value;$('safetyIcon').textContent=value==='CRITICAL'?'!!':value==='WARNING'?'!':'OK';$('safetyTitle').textContent=value==='CRITICAL'?'Phát hiện bất thường nghiêm trọng':value==='WARNING'?'Có dấu hiệu cần kiểm tra':value==='NORMAL'?'Sinh hoạt bình thường':'Hệ thống sẵn sàng';$('safetyDescription').textContent=translateReason((status.reasons||[])[0])||'Không có cảnh báo cần xử lý.';
  document.querySelectorAll('#roomGrid .room-tile').forEach(element=>{const active=element.dataset.room===status.room;element.classList.toggle('active',active);element.querySelector('small').textContent=active?'Đang ở đây':'Không hoạt động';});
  const probabilities=status.smoothed_probabilities||{};$('probabilities').innerHTML=Object.entries(probabilities).map(([room,p])=>`<div class="probability"><span>${escapeHTML(roomLabel(room))} ${(p*100).toFixed(0)}%</span><div><i style="width:${p*100}%"></i></div></div>`).join('');
  const signal=status.signal||{};$('signalDot').className=(signal.quality||'').toLowerCase();$('signalText').textContent=signal.quality?`${signal.visible_access_points} AP • ${{GOOD:'Tín hiệu tốt',FAIR:'Tín hiệu vừa',WEAK:'Tín hiệu yếu'}[signal.quality]||signal.quality}`:'Chưa có tín hiệu';$('lastUpdate').textContent=fmtTime(status.timestamp);
  if(status.calibration)renderCalibration(status.calibration);if(status.mobile_sensor)renderMobileSensor(status.mobile_sensor);
}

function compactHistory(history){const result=[];for(const item of history){const last=result.at(-1);if(!last||last.room!==item.room)result.push(item);else result[result.length-1]=item}return result.slice(-12).reverse()}
function renderHistory(history){const items=compactHistory(history);$('historyCount').textContent=`${items.length} sự kiện`;$('history').innerHTML=items.map((item,index)=>`<div class="timeline-item ${index<items.length-1?'transition':''}"><time>${fmtTime(item.timestamp)}</time><strong>${escapeHTML(roomLabel(item.room))}</strong><span>${item.activity?.state==='ROOM_CHANGE'?'Chuyển phòng':fmtDuration(item.dwell_minutes)}</span></div>`).join('')||'<div class="empty-state">Dữ liệu hoạt động sẽ xuất hiện tại đây.</div>'}
function renderAlerts(alerts){$('alertCount').textContent=alerts.length;$('alertsList').innerHTML=alerts.slice(-6).reverse().map(item=>`<div class="alert ${(item.status||'').toLowerCase()}"><strong>${escapeHTML(item.room||'Cảm biến')} • ${escapeHTML(item.status)}</strong><span>${escapeHTML((item.reasons||[]).map(translateReason).join(' · '))}</span></div>`).join('')||'<div class="empty-state">Chưa có cảnh báo.</div>'}
function renderMetrics(metrics){const room=metrics.room_model||{},anomaly=metrics.anomaly_model||{},baselines=metrics.baselines||{};$('metricAccuracy').textContent=room.accuracy!=null?`${(room.accuracy*100).toFixed(2)}%`:'—';$('metricF1').textContent=room.macro_f1!=null?`${(room.macro_f1*100).toFixed(2)}%`:'—';$('metricRecall').textContent=anomaly.recall!=null?`${(anomaly.recall*100).toFixed(2)}%`:'Chưa train';$('metricLatency').textContent=room.mean_inference_ms!=null?`${room.mean_inference_ms.toFixed(3)} ms`:'—';const comparisons=[['RoomNet-Lite',room.accuracy],...Object.entries(baselines).map(([name,values])=>[name,values?.accuracy])].filter(([,value])=>value!=null);$('baselineComparison').innerHTML=comparisons.map(([name,value])=>`<div><span>${escapeHTML(name)}</span><div><i style="width:${Math.min(100,Math.max(0,value*100))}%"></i></div><strong>${(value*100).toFixed(2)}%</strong></div>`).join('');}

async function refreshDashboard(){if(!state.authenticated||document.hidden)return;try{const [status,history,alerts]=await Promise.all([api('/api/status'),api('/api/history'),api('/api/alerts')]);setConnection(true,status.timestamp);const statusKey=JSON.stringify([status.room,status.status,status.confidence,status.dwell_minutes,status.anomaly_score,status.timestamp,status.activity,status.signal,status.smoothed_probabilities,status.calibration,status.mobile_sensor]);if(statusKey!==lastRenderKey.status){lastRenderKey.status=statusKey;renderStatus(status);}const historyKey=JSON.stringify(history.map(item=>[item.timestamp,item.room,item.dwell_minutes,item.activity?.state]));if(historyKey!==lastRenderKey.history){lastRenderKey.history=historyKey;renderHistory(history);}const alertsKey=JSON.stringify(alerts.map(item=>item.id));if(alertsKey!==lastRenderKey.alerts){lastRenderKey.alerts=alertsKey;renderAlerts(alerts);}}catch(error){if(error.status===401)showAuth();else setConnection(false);}}

async function demoStep(){try{await api('/api/demo/scan',{method:'POST',body:'{}'});await refreshDashboard();}catch(error){stopDemo();$('demoStatus').textContent=`Không chạy được demo: ${error.message}`;}}
function stopDemo(){if(demoTimer)clearInterval(demoTimer);demoTimer=null;state.demoMode=false;document.body.classList.remove('demo-mode');$('demoToggle').classList.remove('running');$('demoToggle').textContent='Chạy demo';$('demoToggle').setAttribute('aria-pressed','false');if(state.calibration)renderCalibration(state.calibration);}
function startDemo(){state.demoMode=true;document.body.classList.add('demo-mode');document.body.classList.remove('calibration-required');$('demoToggle').classList.add('running');$('demoToggle').textContent='Dừng demo';$('demoToggle').setAttribute('aria-pressed','true');$('demoStatus').textContent='Đang phát fingerprint mẫu…';demoStep();demoTimer=setInterval(demoStep,900);}
function toggleDemo(){if(demoTimer){stopDemo();$('demoStatus').textContent='Đã tạm dừng demo.';}else startDemo();}

function renderMobileSensor(sensor){if(!sensor)return;const labels={MOVING:'Đang di chuyển',STILL:'Đang đứng yên',IMPACT_RECORDED:'Ghi nhận va chạm',NO_DATA:'Chưa có dữ liệu'};$('sensorBadge').textContent=labels[sensor.state]||sensor.state;$('sensorBadge').className=`badge ${sensor.possible_impact?'warning':sensor.state==='NO_DATA'?'neutral':'normal'}`;if(sensor.last_seen_at)$('sensorMeta').textContent=`${sensor.samples_received} mẫu • ${Number(sensor.motion_magnitude).toFixed(2)} m/s² • ${fmtTime(sensor.last_seen_at)}`;}
async function sendMotion(acceleration){try{renderMobileSensor(await api('/api/sensor',{method:'POST',body:JSON.stringify({device_id:deviceId,timestamp:Date.now()/1000,acceleration})}));}catch(error){$('sensorMeta').textContent=`Không gửi được dữ liệu: ${error.message}`;}}
function onDeviceMotion(event){const a=event.acceleration;if(!a||a.x==null||a.y==null||a.z==null)return;const magnitude=Math.hypot(a.x,a.y,a.z),now=performance.now();if(magnitude<18&&now-lastSensorSentAt<500)return;lastSensorSentAt=now;sendMotion({x:a.x,y:a.y,z:a.z});}
async function toggleSensor(){if(sensorActive){window.removeEventListener('devicemotion',onDeviceMotion);sensorActive=false;$('sensorToggle').textContent='Bật cảm biến iPhone';$('sensorToggle').setAttribute('aria-pressed','false');return}if(!window.isSecureContext){$('sensorMeta').textContent='Cần HTTPS để Safari cấp quyền.';return}if(typeof DeviceMotionEvent==='undefined'){ $('sensorMeta').textContent='Thiết bị không hỗ trợ DeviceMotion.';return}try{if(typeof DeviceMotionEvent.requestPermission==='function'&&await DeviceMotionEvent.requestPermission()!=='granted')throw new Error('Chưa cấp quyền cảm biến');window.addEventListener('devicemotion',onDeviceMotion,{passive:true});sensorActive=true;$('sensorToggle').textContent='Dừng cảm biến';$('sensorToggle').setAttribute('aria-pressed','true');$('sensorMeta').textContent='Cảm biến hoạt động khi ứng dụng đang mở.';}catch(error){$('sensorMeta').textContent=error.message;}}

async function checkTrainingStatus(){const job=await api('/api/training/status');if(job.status==='TRAINING'){renderTrainingJob(job);if(!trainingTimer)trainingTimer=setInterval(checkTrainingStatus,3000);}else{if(trainingTimer){clearInterval(trainingTimer);trainingTimer=null;}if(job.status==='READY'&&state.calibration?.model_status!=='READY'){state.calibration=await api('/api/calibration');renderCalibration(state.calibration);await api('/api/metrics').then(renderMetrics);}renderTrainingJob(job);}}
function renderTrainingJob(job){if(job.status==='TRAINING'){$('trainingTitle').textContent='Đang huấn luyện model';$('trainingMeta').textContent='Không tắt máy chủ. Quá trình có thể mất vài phút.';$('trainButton').disabled=true;}else if(job.status==='FAILED'){$('trainingTitle').textContent='Huấn luyện thất bại';$('trainingMeta').textContent=job.message||'Kiểm tra dữ liệu và thử lại.';} }

$('loginTab').addEventListener('click',()=>selectAuthTab('login'));$('registerTab').addEventListener('click',()=>selectAuthTab('register'));
$('loginForm').addEventListener('submit',event=>{event.preventDefault();submitAuth(event.currentTarget,'/api/auth/login');});$('registerForm').addEventListener('submit',event=>{event.preventDefault();submitAuth(event.currentTarget,'/api/auth/register');});
$('logoutButton').addEventListener('click',async()=>{await api('/api/auth/logout',{method:'POST'});location.reload();});
$('homeSelect').addEventListener('change',async event=>{await api(`/api/homes/${event.target.value}/select`,{method:'POST'});state.me=await api('/api/auth/me');renderHomes();await loadHome();});
$('addHomeButton').addEventListener('click',()=>$('homeDialog').showModal());document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.close).close()));
$('homeForm').addEventListener('submit',async event=>{event.preventDefault();const button=event.currentTarget.querySelector('[type="submit"]');setButtonBusy(button,true);try{await api('/api/homes',{method:'POST',body:JSON.stringify({name:$('newHomeName').value})});$('homeDialog').close();$('newHomeName').value='';state.me=await api('/api/auth/me');renderHomes();await loadHome();}finally{setButtonBusy(button,false);}});
$('roomForm').addEventListener('submit',async event=>{event.preventDefault();const button=event.currentTarget.querySelector('button');setButtonBusy(button,true);try{await api('/api/rooms',{method:'POST',body:JSON.stringify({name:$('newRoomName').value,max_dwell_minutes:Number($('newRoomDwell').value)})});$('newRoomName').value='';await loadHome();}catch(error){alert(error.message)}finally{setButtonBusy(button,false);}});
$('deviceForm').addEventListener('submit',async event=>{event.preventDefault();const button=event.currentTarget.querySelector('button');setButtonBusy(button,true);try{const result=await api('/api/devices',{method:'POST',body:JSON.stringify({name:$('deviceName').value,platform:'android'})});$('deviceToken').value=result.token;$('tokenReveal').hidden=false;state.devices=await api('/api/devices');renderDevices();renderCalibration(state.calibration);}finally{setButtonBusy(button,false);}});
$('copyToken').addEventListener('click',async()=>{const value=$('deviceToken').value;try{await navigator.clipboard.writeText(value);$('copyToken').textContent='Đã sao chép';}catch{$('deviceToken').select();document.execCommand('copy');}});
$('trainButton').addEventListener('click',async()=>{setButtonBusy($('trainButton'),true,'Đang khởi động…');try{await api('/api/training/start',{method:'POST'});checkTrainingStatus();}catch(error){alert(error.message);setButtonBusy($('trainButton'),false);}});
$('demoFromLock').addEventListener('click',startDemo);$('demoToggle').addEventListener('click',toggleDemo);$('sensorToggle').addEventListener('click',toggleSensor);
$('resetBtn').addEventListener('click',async()=>{if(!confirm('Đặt lại trạng thái tạm thời? Dữ liệu SQLite vẫn được giữ.'))return;await api('/api/reset',{method:'POST'});stopDemo();state.demoMode=false;document.body.classList.remove('demo-mode');renderCalibration(state.calibration);await refreshDashboard();});
$('installButton').addEventListener('click',()=>$('installGuide').showModal());
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopDemo();else refreshDashboard();});

const isIOS=/iphone|ipad|ipod/i.test(navigator.userAgent),isStandalone=matchMedia('(display-mode: standalone)').matches||navigator.standalone;if(isIOS&&!isStandalone)$('installButton').hidden=false;
if('serviceWorker'in navigator)navigator.serviceWorker.register('/service-worker.js').catch(console.error);
loadApplication().catch(error=>{console.error(error);showAuth(false);});
