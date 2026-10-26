const POLL_MS = 1500;
const ROOM_NAMES = {Bedroom:'Phòng ngủ',Corridor:'Hành lang',Bathroom:'Phòng tắm',LivingRoom:'Phòng khách',Kitchen:'Nhà bếp'};
const ACTIVITY = {
  CALIBRATING:['Đang hiệu chuẩn','Cần vài mẫu tín hiệu đầu tiên','…'],
  STILL:['Đang nghỉ ngơi','Không ghi nhận biến động đáng kể','○'],
  LIGHT_ACTIVITY:['Hoạt động nhẹ','Tín hiệu thay đổi nhẹ trong phòng','≈'],
  MOVING:['Đang di chuyển','Phát hiện biến động tín hiệu Wi‑Fi','→'],
  ROOM_CHANGE:['Vừa chuyển phòng','Đã xác nhận thay đổi vị trí','↗']
};
let demoTimer = null;

const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
function fmtTime(ts){return ts ? new Date(ts*1000).toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit'}) : '—'}
function fmtDuration(minutes){if(minutes==null)return '—';if(minutes<1)return `${Math.round(minutes*60)} giây`;if(minutes<60)return `${minutes.toFixed(1)} phút`;return `${Math.floor(minutes/60)}g ${Math.round(minutes%60)}p`}
async function loadJSON(url,options){const res=await fetch(url+(options?'':`?t=${Date.now()}`),options);if(!res.ok)throw new Error(`${res.status} ${res.statusText}`);return res.json()}

function setConnection(ok){$('statusDot').className=ok?'live':'error';$('statusText').textContent=ok?'Hệ thống trực tuyến':'Mất kết nối'}
function renderStatus(s){
  const roomName=ROOM_NAMES[s.room]||s.room||'Chưa có dữ liệu';
  $('room').textContent=roomName;
  $('roomMeta').textContent=s.room?`${s.room} • định vị mức phòng`:'Đang chờ fingerprint Wi‑Fi…';
  $('confidence').textContent=s.confidence!=null?`TIN CẬY ${(s.confidence*100).toFixed(0)}%`:'—';
  $('dwell').textContent=fmtDuration(s.dwell_minutes);
  $('score').textContent=s.anomaly_score!=null?s.anomaly_score.toFixed(3):'Đang học';
  const ratio=s.anomaly_score!=null&&s.anomaly_threshold?Math.min(100,s.anomaly_score/s.anomaly_threshold*100):0;
  $('meterFill').style.width=`${ratio}%`;

  const activity=s.activity||{};const copy=ACTIVITY[activity.state]||ACTIVITY.CALIBRATING;
  $('activityState').textContent=copy[0];$('activityMeta').textContent=copy[1];$('activityIcon').textContent=copy[2];
  $('transitions').textContent=activity.transitions_last_hour??'—';

  const status=(s.status||'NO_DATA').toUpperCase();const safetyCard=$('safetyCard');
  safetyCard.className=`card safety-card ${status.toLowerCase()}`;
  $('systemBadge').className=`badge ${status==='NO_DATA'?'neutral':status.toLowerCase()}`;
  $('systemBadge').textContent={NORMAL:'AN TOÀN',WARNING:'CẦN CHÚ Ý',CRITICAL:'KHẨN CẤP',NO_DATA:'CHƯA CÓ DỮ LIỆU'}[status]||status;
  $('safetyIcon').textContent=status==='CRITICAL'?'!':status==='WARNING'?'△':'✓';
  $('safetyTitle').textContent=status==='CRITICAL'?'Phát hiện bất thường nghiêm trọng':status==='WARNING'?'Có dấu hiệu cần kiểm tra':status==='NORMAL'?'Sinh hoạt bình thường':'Hệ thống sẵn sàng';
  $('safetyDescription').textContent=(s.reasons||[])[0]||'Không có cảnh báo cần xử lý.';

  document.querySelectorAll('.room-tile').forEach(el=>el.classList.toggle('active',el.dataset.room===s.room));
  const probs=s.smoothed_probabilities||{};
  $('probabilities').innerHTML=Object.entries(probs).map(([room,p])=>`<div class="probability"><span>${escapeHTML(ROOM_NAMES[room]||room)} ${(p*100).toFixed(0)}%</span><div><i style="width:${p*100}%"></i></div></div>`).join('');

  const signal=s.signal||{};const quality=(signal.quality||'').toLowerCase();
  $('signalDot').className=quality;$('signalText').textContent=signal.quality?`${signal.visible_access_points} AP • ${ {GOOD:'Tín hiệu tốt',FAIR:'Tín hiệu vừa',WEAK:'Tín hiệu yếu'}[signal.quality]||signal.quality}`:'Chưa có tín hiệu';
  $('lastUpdate').textContent=fmtTime(s.timestamp);
}

function compactHistory(history){const result=[];for(const item of history){const last=result[result.length-1];if(!last||last.room!==item.room)result.push(item);else result[result.length-1]=item}return result.slice(-12).reverse()}
function renderHistory(history){const items=compactHistory(history);$('historyCount').textContent=`${items.length} sự kiện`;$('history').innerHTML=items.map((x,i)=>`<div class="timeline-item ${i<items.length-1?'transition':''}"><time>${fmtTime(x.timestamp)}</time><strong>${escapeHTML(ROOM_NAMES[x.room]||x.room)}</strong><span>${x.activity?.state==='ROOM_CHANGE'?'Chuyển phòng':fmtDuration(x.dwell_minutes)}</span></div>`).join('')||'<div class="empty-state">Dữ liệu hoạt động sẽ xuất hiện tại đây.</div>'}
function renderAlerts(alerts){$('alertCount').textContent=alerts.length;$('alertsList').innerHTML=alerts.slice(-6).reverse().map(x=>`<div class="alert ${(x.status||'').toLowerCase()}"><strong>${escapeHTML(ROOM_NAMES[x.room]||x.room)} • ${escapeHTML(x.status)}</strong><span>${escapeHTML((x.reasons||[]).join(' · '))}</span></div>`).join('')||'<div class="empty-state">Chưa có cảnh báo.</div>'}

async function refresh(){try{const [status,history,alerts]=await Promise.all([loadJSON('/api/status'),loadJSON('/api/history'),loadJSON('/api/alerts')]);renderStatus(status);renderHistory(history);renderAlerts(alerts);setConnection(true)}catch(error){console.error(error);setConnection(false)}}
async function demoStep(room){try{await loadJSON('/api/demo/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(room?{room}:{})});await refresh()}catch(error){stopDemo();$('demoStatus').textContent=`Không thể chạy demo: ${error.message}`}}
function stopDemo(){if(demoTimer)clearInterval(demoTimer);demoTimer=null;$('demoToggle').classList.remove('running');$('demoToggle').textContent='▶ Chạy demo'}
function toggleDemo(){if(demoTimer){stopDemo();$('demoStatus').textContent='Đã tạm dừng mô phỏng.';return}$('demoToggle').classList.add('running');$('demoToggle').textContent='■ Dừng demo';$('demoStatus').textContent='Đang phát fingerprint mẫu…';demoStep();demoTimer=setInterval(()=>demoStep(),900)}
async function selectDemoRoom(room){stopDemo();$('demoStatus').textContent=`Đang mô phỏng ${ROOM_NAMES[room]||room}…`;for(let i=0;i<6;i+=1)await demoStep(room);$('demoStatus').textContent=`Đã gửi fingerprint của ${ROOM_NAMES[room]||room}.`}

$('demoToggle').addEventListener('click',toggleDemo);
$('resetBtn').addEventListener('click',async()=>{stopDemo();await loadJSON('/api/reset',{method:'POST'});$('demoStatus').textContent='Đã đặt lại phiên giám sát.';await refresh()});
document.querySelectorAll('.room-tile').forEach(button=>button.addEventListener('click',()=>selectDemoRoom(button.dataset.room)));
refresh();setInterval(refresh,POLL_MS);
