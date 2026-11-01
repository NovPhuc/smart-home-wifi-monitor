package com.example.wificollector

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import org.json.JSONObject
import java.net.CookieHandler
import java.net.CookieManager
import java.net.CookiePolicy
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.security.KeyStore
import java.security.MessageDigest
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSession
import javax.net.ssl.TrustManagerFactory
import javax.net.ssl.X509TrustManager
import kotlin.concurrent.thread
import kotlin.math.abs

/**
 * Ghim chứng chỉ server (certificate pinning) cho các kết nối HTTPS.
 *
 * Chỉ áp dụng cho URL https:// (domain/tunnel ra ngoài LAN). Kết nối HTTP
 * trong mạng LAN do NSD tự phát hiện không đi qua ghim — HTTP không có
 * chứng chỉ để ghim; ranh giới tin cậy của mạng LAN nhà là điểm truy cập WiFi.
 *
 * Pin lấy từ res/raw/cert_pins.txt (một pin mỗi dòng, định dạng
 * "sha256/<base64 SPKI>"). Sinh pin bằng:
 *   openssl x509 -in cert.pem -pubkey -noout | openssl pkey -pubin -outform DER \
 *     | openssl dgst -sha256 -binary | base64
 *
 * QUAN TRỌNG — ghim là lớp TĂNG CƯỜNG, không thay thế việc xác thực chuỗi
 * chứng chỉ. TrustManager tự viết ở đây luôn uỷ thác cho TrustManager mặc định
 * của hệ thống trước, rồi mới kiểm tra pin. Khi chưa điền pin (đúng trạng thái
 * mặc định của res/raw/cert_pins.txt), pinnedSslContext() trả về null để bên
 * gọi giữ nguyên cấu hình mặc định của Android.
 *
 * Bản trước đây luôn cài một TrustManager chỉ kiểm tra hạn dùng chứng chỉ và
 * chỉ kiểm tra pin khi có pin — nghĩa là ở trạng thái mặc định, app chấp nhận
 * MỌI chứng chỉ tự ký, và HostnameVerifier trả về true cho mọi tên miền. Cả
 * hai đều bị vá ở đây.
 */
object CertificatePinner {
    private const val TAG = "CertificatePinner"

    private fun loadPins(context: Context?): List<String> {
        if (context == null) return emptyList()
        return try {
            context.resources.openRawResource(R.raw.cert_pins).bufferedReader().readLines()
                .map { it.trim() }
                .filter { it.isNotEmpty() && !it.startsWith("#") }
        } catch (_: Exception) {
            emptyList()
        }
    }

    /** Băm SPKI (phần public key) của chứng chỉ về dạng "sha256/<base64>". */
    private fun pinOf(cert: X509Certificate): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(cert.publicKey.encoded)
        return "sha256/" + android.util.Base64.encodeToString(digest, android.util.Base64.NO_WRAP)
    }

    /**
     * TrustManager mặc định của hệ thống — thứ thực hiện xác thực chuỗi chứng
     * chỉ tới root tin cậy. TrustManager tự viết không được phép thay thế nó.
     */
    private fun defaultTrustManager(): X509TrustManager {
        val factory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())
        factory.init(null as KeyStore?)
        return factory.trustManagers.filterIsInstance<X509TrustManager>().first()
    }

    /**
     * SSLContext có ghim pin, hoặc **null** khi chưa cấu hình pin.
     *
     * Trả về null là chủ đích: bên gọi phải giữ SSLContext mặc định của hệ
     * thống, thay vì cài một TrustManager tự viết không kiểm tra root.
     */
    fun pinnedSslContext(context: Context?): SSLContext? {
        val pins = loadPins(context)
        if (pins.isEmpty()) return null
        val default = defaultTrustManager()
        val trustManager = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>?, authType: String?) =
                default.checkClientTrusted(chain, authType)

            override fun checkServerTrusted(chain: Array<X509Certificate>?, authType: String?) {
                // 1) Xác thực chuỗi tới root tin cậy bằng trust store hệ thống.
                default.checkServerTrusted(chain, authType)
                // 2) Rồi mới siết thêm bằng pin.
                if (chain.isNullOrEmpty() || chain.none { pinOf(it) in pins }) {
                    throw CertificateException("Certificate pinning thất bại cho server")
                }
            }

            override fun getAcceptedIssuers(): Array<X509Certificate> = default.acceptedIssuers
        }
        return SSLContext.getInstance("TLS").apply { init(null, arrayOf(trustManager), null) }
    }

    /**
     * Kiểm tra tên miền rồi tới pin, dùng cho HostnameVerifier.
     *
     * Luôn chạy kiểm tra tên miền mặc định trước; chưa có pin thì dừng ở đó
     * (đúng hành vi mặc định của Android). Bản cũ trả về true ngay khi chưa có
     * pin nên đã tắt luôn cả kiểm tra tên miền.
     */
    fun verifyHostname(hostname: String, session: SSLSession, context: Context?): Boolean {
        if (!HttpsURLConnection.getDefaultHostnameVerifier().verify(hostname, session)) return false
        val pins = loadPins(context)
        if (pins.isEmpty()) return true
        val peer = session.peerCertificates
        if (peer.isNullOrEmpty()) return false
        return peer.any { it is X509Certificate && pinOf(it) in pins }
    }
}

class MainActivity : AppCompatActivity(), SensorEventListener {
    private lateinit var wifiManager: WifiManager
    private lateinit var sensorManager: SensorManager
    private var accelerometer: Sensor? = null
    private lateinit var backendUrl: EditText
    private lateinit var loginEmail: EditText
    private lateinit var loginPassword: EditText
    private lateinit var collectorToken: EditText
    private lateinit var joinCode: EditText
    private lateinit var discoveryStatus: TextView
    private lateinit var shareCodeText: TextView
    private lateinit var roomName: EditText
    private lateinit var sessionId: EditText
    private lateinit var orientationText: TextView
    private lateinit var statusText: TextView
    private lateinit var roomHero: TextView
    private lateinit var statusChip: TextView
    private lateinit var confBar: ProgressBar
    private lateinit var confText: TextView
    private lateinit var statActivity: TextView
    private lateinit var statSignal: TextView
    private lateinit var statDwell: TextView
    private lateinit var apsBadge: TextView
    private lateinit var inferButton: Button
    private lateinit var autoButton: Button
    private lateinit var autoCollectButton: Button
    private var autoScanJob: Thread? = null
    private var autoCollectJob: Thread? = null
    private var nsdManager: NsdManager? = null
    private var nsdDiscovering = false
    @Volatile private var activeHomeId: Int = -1
    @Volatile private var activeHomeRole: String = ""

    @Volatile
    private var autoRunning = false
    @Volatile private var autoCollectRunning = false
    @Volatile private var currentOrientation = "UNKNOWN"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager
        accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        backendUrl = findViewById(R.id.backendUrl)
        loginEmail = findViewById(R.id.loginEmail)
        loginPassword = findViewById(R.id.loginPassword)
        joinCode = findViewById(R.id.joinCode)
        discoveryStatus = findViewById(R.id.discoveryStatus)
        shareCodeText = findViewById(R.id.shareCodeText)
        collectorToken = findViewById(R.id.collectorToken)
        roomName = findViewById(R.id.roomName)
        sessionId = findViewById(R.id.sessionId)
        orientationText = findViewById(R.id.orientationText)
        statusText = findViewById(R.id.statusText)
        roomHero = findViewById(R.id.roomHero)
        statusChip = findViewById(R.id.statusChip)
        confBar = findViewById(R.id.confBar)
        confText = findViewById(R.id.confText)
        statActivity = findViewById(R.id.statActivity)
        statSignal = findViewById(R.id.statSignal)
        statDwell = findViewById(R.id.statDwell)
        apsBadge = findViewById(R.id.apsBadge)
        inferButton = findViewById(R.id.inferButton)
        autoButton = findViewById(R.id.autoButton)
        autoCollectButton = findViewById(R.id.autoCollectButton)

        val prefs = getSharedPreferences("wifi-collector", Context.MODE_PRIVATE)
        backendUrl.setText(prefs.getString("backendUrl", "http://192.168.1.10:5000"))
        loginEmail.setText(prefs.getString("loginEmail", ""))
        collectorToken.setText(prefs.getString("collectorToken", ""))
        roomName.setText(prefs.getString("roomName", ""))
        sessionId.setText(prefs.getString("sessionId", "android-session"))

        restoreSessionCookie()
        requestRuntimePermissions()
        startServerDiscovery()

        findViewById<Button>(R.id.discoverButton).setOnClickListener { startServerDiscovery() }
        findViewById<Button>(R.id.loginButton).setOnClickListener { loginAndLoadHome() }
        findViewById<Button>(R.id.joinButton).setOnClickListener { joinHomeByCode() }
        findViewById<Button>(R.id.shareButton).setOnClickListener { createShareCode() }
        findViewById<Button>(R.id.collectButton).setOnClickListener { captureAndSend(collection = true) }
        autoCollectButton.setOnClickListener {
            if (autoCollectRunning) stopAutoCollect() else startAutoCollect()
        }
        inferButton.setOnClickListener { captureAndSend(collection = false) }
        autoButton.setOnClickListener {
            if (autoRunning) stopAutoScan() else startAutoScan()
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != PERMISSIONS_REQUEST_CODE) return
        if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
            log("Đã cấp quyền. Sẵn sàng quét Wi-Fi.")
        } else {
            log("Thiếu quyền vị trí/Wi-Fi — không thể đọc scan results.")
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        stopAutoScan()
        stopAutoCollect()
    }

    override fun onResume() {
        super.onResume()
        accelerometer?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL) }
    }

    override fun onPause() {
        super.onPause()
        sensorManager.unregisterListener(this)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

    override fun onSensorChanged(event: SensorEvent?) {
        if (event?.sensor?.type != Sensor.TYPE_ACCELEROMETER) return
        val x = event.values[0]
        val y = event.values[1]
        val z = event.values[2]
        currentOrientation = when {
            abs(z) > 7f -> if (z > 0) "FLAT_UP" else "FLAT_DOWN"
            abs(x) > abs(y) -> if (x > 0) "LANDSCAPE_LEFT" else "LANDSCAPE_RIGHT"
            else -> if (y > 0) "PORTRAIT_UP" else "PORTRAIT_DOWN"
        }
        runOnUiThread { orientationText.text = "Hướng cầm: $currentOrientation" }
    }

    // ─── UI helpers ─────────────────────────────────────────────

    private fun log(message: String) {
        runOnUiThread { statusText.text = message }
    }

    private fun setBusy(busy: Boolean) {
        runOnUiThread {
            inferButton.isEnabled = !busy
            collectButtonEnabled(!busy)
            if (busy) {
                autoButton.setTextColor(Color.parseColor("#64748B"))
            } else {
                autoButton.setTextColor(Color.parseColor("#F1F5F9"))
            }
        }
    }

    private fun collectButtonEnabled(enabled: Boolean) {
        findViewById<Button>(R.id.collectButton).isEnabled = enabled
    }

    private fun showResult(json: JSONObject) {
        runOnUiThread {
            val room = json.optString("room", "").ifEmpty { "— — —" }
            val status = json.optString("status", "")
            roomHero.text = room

            val confidence = when {
                json.has("confidence") -> json.optDouble("confidence")
                else -> -1.0
            }
            if (confidence >= 0) {
                val pct = (confidence * 100).toInt().coerceIn(0, 100)
                confBar.progress = pct
                confText.text = "$pct%"
            } else {
                confBar.progress = 0
                confText.text = "—"
            }

            val activity = json.optJSONObject("activity")
            statActivity.text = activity?.optString("state", "—")?.ifEmpty { "—" } ?: "—"
            statSignal.text = json.optJSONObject("signal")?.optString("quality", "—")?.ifEmpty { "—" } ?: "—"
            val dwell = json.optDouble("dwell_minutes", -1.0)
            statDwell.text = if (dwell >= 0) String.format("%.0f min", dwell) else "—"

            val chipColor = when (status.uppercase()) {
                "CRITICAL" -> "#F87171"
                "WARNING" -> "#FBBF24"
                "NORMAL" -> "#34D399"
                "COLLECTING" -> "#22D3EE"
                else -> "#22D3EE"
            }
            statusChip.setTextColor(Color.parseColor(chipColor))
            statusChip.text = status.ifEmpty { "READY" }

            val reasons = json.optJSONArray("reasons")
            if (reasons != null && reasons.length() > 0) {
                val parts = (0 until reasons.length()).map { reasons.optString(it) }
                log("⚠ " + parts.joinToString(" | "))
            }
        }
    }

    private fun showCollectAck(json: JSONObject) {
        runOnUiThread {
            val aps = json.optInt("aps", 0)
            val samples = json.optInt("samples", 0)
            val target = json.optInt("target_samples", 100)
            val orientations = json.optInt("orientations", 0)
            apsBadge.text = "$aps APs"
            log("Đã lưu $samples/$target mẫu • $orientations hướng cầm • $aps AP")
        }
    }

    private fun savePrefs() {
        val prefs = getSharedPreferences("wifi-collector", Context.MODE_PRIVATE)
        prefs.edit()
            .putString("backendUrl", backendUrl.text.toString().trim())
            .putString("loginEmail", loginEmail.text.toString().trim())
            .putString("collectorToken", collectorToken.text.toString().trim())
            .putString("roomName", roomName.text.toString().trim())
            .putString("sessionId", sessionId.text.toString().trim())
            .apply()
    }

    // ─── NSD: tự tìm máy chủ trên WiFi nhà ──────────────────────

    private var discoveryListener: NsdManager.DiscoveryListener? = null

    private fun startServerDiscovery() {
        val manager = nsdManager ?: (getSystemService(Context.NSD_SERVICE) as NsdManager).also { nsdManager = it }
        val listener = discoveryListener ?: buildDiscoveryListener(manager).also { discoveryListener = it }
        if (nsdDiscovering) return
        nsdDiscovering = true
        runOnUiThread {
            discoveryStatus.text = "Đang dò tìm máy chủ An Tâm trên WiFi…"
        }
        try {
            manager.discoverServices("_antam._tcp.", NsdManager.PROTOCOL_DNS_SD, listener)
        } catch (e: Exception) {
            nsdDiscovering = false
            runOnUiThread { discoveryStatus.text = "Không dò được (${e.message}) — nhập URL thủ công." }
        }
    }

    private fun buildDiscoveryListener(manager: NsdManager) = object : NsdManager.DiscoveryListener {
        override fun onDiscoveryStarted(serviceType: String) {
            runOnUiThread { discoveryStatus.text = "Đang quét WiFi của nhà… (máy chủ phải cùng mạng)" }
        }

        override fun onServiceFound(serviceInfo: NsdServiceInfo) {
            // Dừng quét và giải địa chỉ của máy chủ đầu tiên tìm thấy.
            try { manager.stopServiceDiscovery(this) } catch (_: Exception) {}
            nsdDiscovering = false
            runOnUiThread { discoveryStatus.text = "Đã thấy máy chủ “${serviceInfo.serviceName}” — đang giải địa chỉ…" }
            manager.resolveService(serviceInfo, object : NsdManager.ResolveListener {
                override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {
                    runOnUiThread { discoveryStatus.text = "Không giải được địa chỉ máy chủ (mã $errorCode) — nhập tay." }
                }

                override fun onServiceResolved(info: NsdServiceInfo) {
                    val host = info.host?.hostAddress?.ifEmpty { null }
                        ?: info.serviceName
                    val url = "http://$host:${info.port}"
                    runOnUiThread {
                        backendUrl.setText(url)
                        discoveryStatus.text = "Máy chủ: $url"
                        log("Tự tìm thấy máy chủ qua NSD: $url")
                    }
                }
            })
        }

        override fun onServiceLost(serviceInfo: NsdServiceInfo) {
            runOnUiThread { discoveryStatus.text = "Máy chủ mất khỏi mạng — thử “Tìm lại máy chủ”." }
        }

        override fun onDiscoveryStopped(serviceType: String) { nsdDiscovering = false }
        override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
            nsdDiscovering = false
            runOnUiThread { discoveryStatus.text = "Bật dò tìm thất bại (mã $errorCode) — nhập tay." }
        }
        override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) { nsdDiscovering = false }
    }

    // ─── Cookie phiên đăng nhập (không cần gõ IP lần sau) ────────

    private fun restoreSessionCookie() {
        val cookieHandler = CookieManager()
        cookieHandler.setCookiePolicy(CookiePolicy.ACCEPT_ORIGINAL_SERVER)
        CookieHandler.setDefault(cookieHandler)
        val prefs = getSharedPreferences("wifi-collector", Context.MODE_PRIVATE)
        val saved = prefs.getString("sessionCookie", null) ?: return
        val savedUrl = prefs.getString("sessionUrl", null) ?: return
        try {
            cookieHandler.put(URI(savedUrl), mapOf("Cookie" to listOf("session=$saved")))
            log("Khôi phục phiên đăng nhập đã lưu (không cần gõ IP và đăng nhập lại).")
        } catch (_: Exception) {
        }
    }

    private fun persistSessionCookie() {
        val cookieHandler = CookieHandler.getDefault() as? CookieManager ?: return
        val baseUrl = backendUrl.text.toString().trim()
        if (!baseUrl.startsWith("http")) return
        val session = try {
            cookieHandler.get(URI(baseUrl), emptyMap<String, List<String>>())
                ?.get("Cookie")?.firstOrNull { it.startsWith("session=") }?.removePrefix("session=")
        } catch (_: Exception) { null } ?: return
        getSharedPreferences("wifi-collector", Context.MODE_PRIVATE).edit()
            .putString("sessionCookie", session)
            .putString("sessionUrl", baseUrl.trimEnd('/') + "/")
            .apply()
    }

    // ─── Tài khoản + chia sẻ nhà theo mã 6 số ───────────────────

    private fun loginAndLoadHome() {
        savePrefs()
        val email = loginEmail.text.toString().trim()
        val password = loginPassword.text.toString()
        if (!email.contains("@") || password.isEmpty()) {
            log("Nhập email và mật khẩu để đăng nhập.")
            return
        }
        val base = backendUrl.text.toString().trim().trimEnd('/')
        thread {
            val payload = JSONObject().apply { put("email", email); put("password", password) }
            val (code, body) = httpPost("$base/api/auth/login", payload)
            if (code !in 200..299) {
                log("Đăng nhập thất bại (HTTP $code): ${body.take(120)}")
                return@thread
            }
            persistSessionCookie()
            val (meCode, meBody) = httpGet("$base/api/auth/me")
            if (meCode !in 200..299) {
                log("Đăng nhập được nhưng không đọc được nhà (HTTP $meCode).")
                return@thread
            }
            val me = JSONObject(meBody)
            val homes = me.optJSONArray("homes")
            val active = me.optJSONObject("active_home")
            activeHomeId = active?.optInt("id", -1) ?: -1
            activeHomeRole = active?.optString("role", "") ?: ""
            val shareHint = if (activeHomeRole == "member") " (được chia sẻ — chỉ xem)" else " (chủ nhà)"
            runOnUiThread {
                loginPassword.setText("")
                log("Đã đăng nhập: ${me.optJSONObject("user")?.optString("display_name", "?")} • Nhà: " +
                    "${active?.optString("name", "—")}$shareHint • ${homes?.length() ?: 0} nhà")
            }
        }
    }

    private fun joinHomeByCode() {
        savePrefs()
        val code = joinCode.text.toString().trim()
        if (code.length != 6 || !code.all { it.isDigit() }) {
            log("Mã chia sẻ phải gồm 6 chữ số.")
            return
        }
        val base = backendUrl.text.toString().trim().trimEnd('/')
        thread {
            val payload = JSONObject().apply { put("code", code) }
            val (code_, body) = httpPost("$base/api/homes/join", payload)
            if (code_ == 401) {
                log("Cần đăng nhập tài khoản trước khi tham gia nhà.")
            } else if (code_ !in 200..299) {
                log("Tham gia thất bại (HTTP $code_): ${body.take(140)}")
            } else {
                val joined = JSONObject(body).optJSONObject("joined_home")
                runOnUiThread {
                    joinCode.setText("")
                    shareCodeText.text = ""
                    log("Đã tham gia nhà “${joined?.optString("name", "?")}” (chỉ xem).")
                }
                switchActiveHome("$base", joined?.optInt("id", -1) ?: -1)
            }
        }
    }

    private fun switchActiveHome(base: String, homeId: Int) {
        if (homeId <= 0) return
        thread {
            val (_, body) = httpPost("$base/api/homes/$homeId/select", JSONObject().apply {})
            val me = if (body.isNotBlank()) JSONObject(body) else null
            val ok = me?.has("active_home") == true
            runOnUiThread { if (ok) log("Đã chuyển sang nhà được chia sẻ.") }
        }
    }

    private fun createShareCode() {
        savePrefs()
        if (activeHomeId <= 0 || activeHomeRole == "member") {
            log("Cần đăng nhập với tư cách chủ nhà trước khi tạo mã chia sẻ.")
            return
        }
        val base = backendUrl.text.toString().trim().trimEnd('/')
        runOnUiThread { shareCodeText.text = "Đang tạo mã…" }
        thread {
            val (_, body) = httpPost("$base/api/homes/$activeHomeId/share", JSONObject().apply {})
            if (body.isBlank()) return@thread
            val share = JSONObject(body).optJSONObject("share")
            val code = share?.optString("code").orEmpty()
            val expires = share?.optDouble("expires_at", 0.0) ?: 0.0
            val hoursLeft = ((expires - System.currentTimeMillis() / 1000.0) / 3600).coerceAtLeast(0.0)
            runOnUiThread {
                if (code.isNotBlank()) {
                    shareCodeText.text = "Mã chia sẻ: $code (còn ${hoursLeft.toInt()} giờ)"
                    log("Nhập mã $code trên tài khoản người thân để họ theo dõi nhà này.")
                } else {
                    shareCodeText.text = "Không tạo được mã — kiểm tra quyền chủ nhà."
                }
            }
        }
    }

    // ─── Permissions ────────────────────────────────────────────

    private fun requiredPermissions(): List<String> {
        val permissions = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION)
        if (Build.VERSION.SDK_INT >= 33) permissions.add(Manifest.permission.NEARBY_WIFI_DEVICES)
        return permissions
    }

    private fun hasAllPermissions(): Boolean =
        requiredPermissions().all { ActivityCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED }

    private fun requestRuntimePermissions() {
        val missing = requiredPermissions().filter { ActivityCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) ActivityCompat.requestPermissions(this, missing.toTypedArray(), PERMISSIONS_REQUEST_CODE)
    }

    // ─── Scan + send ────────────────────────────────────────────

    private fun captureAndSend(collection: Boolean) {
        savePrefs()
        val hasToken = collectorToken.text.toString().trim().isNotEmpty()
        val hasSession = hasSessionCookie()
        if (!hasToken && !hasSession) {
            log("Cần mã ghép nối (ath_...) hoặc đăng nhập tài khoản trước.")
            return
        }
        if (!hasAllPermissions()) {
            log("Thiếu quyền vị trí/Wi-Fi để đọc scan results.")
            requestRuntimePermissions()
            return
        }
        try { wifiManager.startScan() } catch (_: SecurityException) { }
        val results = try { wifiManager.scanResults } catch (e: SecurityException) {
            log("Không đọc được Wi-Fi scan: ${e.message}"); return
        }
        if (results.isEmpty()) {
            log("Không có AP nào trong scan results. Chờ 1–2s rồi thử lại.")
            return
        }

        val wifiJson = JSONObject()
        results.forEach { r -> wifiJson.put(hashBssid(r.BSSID), r.level) }
        val payload = JSONObject().apply {
            put("timestamp", System.currentTimeMillis() / 1000.0)
            // Thời điểm quét thật (epoch giây) theo ScanResult.timestamp (micro
            // giây kể từ boot) — server dùng để nhận diện bản ghi trùng khi retry.
            put("scan_timestamp", scanTimestampSeconds(results))
            put("device_id", Build.MODEL ?: "android-phone")
            put("wifi", wifiJson)
            put("orientation", currentOrientation)
            if (collection) {
                put("room", roomName.text.toString().trim())
                put("session_id", sessionId.text.toString().trim())
            }
        }
        val endpoint = if (collection) "/api/collect" else "/api/scan"
        postJson(backendUrl.text.toString().trim().trimEnd('/') + endpoint, payload)
    }

    private fun startAutoScan() {
        if (!hasAllPermissions()) {
            log("Thiếu quyền vị trí/Wi-Fi để đọc scan results.")
            requestRuntimePermissions()
            return
        }
        stopAutoCollect()
        autoRunning = true
        autoButton.text = "STOP"
        autoButton.setTextColor(Color.parseColor("#F87171"))
        log("Auto infer đang chạy (3s/lần)...")
        autoScanJob = thread {
            while (autoRunning) {
                runOnUiThread { captureAndSend(collection = false) }
                try { Thread.sleep(3000) } catch (_: InterruptedException) { break }
            }
        }
    }

    private fun startAutoCollect() {
        if (roomName.text.toString().trim().isEmpty() || sessionId.text.toString().trim().isEmpty()) {
            log("Nhập đúng tên phòng và mã phiên trước khi thu tự động.")
            return
        }
        stopAutoScan()
        autoCollectRunning = true
        autoCollectButton.text = "DỪNG THU"
        autoCollectButton.setTextColor(Color.parseColor("#F87171"))
        log("Đang thu liên tục. Hãy đi quanh phòng và đổi hướng cầm điện thoại.")
        autoCollectJob = thread {
            while (autoCollectRunning) {
                runOnUiThread { captureAndSend(collection = true) }
                try { Thread.sleep(3000) } catch (_: InterruptedException) { break }
            }
        }
    }

    private fun stopAutoCollect() {
        autoCollectRunning = false
        autoCollectJob?.interrupt()
        autoCollectJob = null
        runOnUiThread {
            if (::autoCollectButton.isInitialized) {
                autoCollectButton.text = "THU TỰ ĐỘNG"
                autoCollectButton.setTextColor(Color.parseColor("#06121F"))
            }
        }
    }

    private fun stopAutoScan() {
        autoRunning = false
        autoScanJob?.interrupt()
        autoScanJob = null
        runOnUiThread {
            findViewById<Button>(R.id.autoButton)?.let {
                it.text = "AUTO"
                it.setTextColor(Color.parseColor("#F1F5F9"))
            }
        }
    }

    private fun hashBssid(bssid: String): String {
        // Viết thường trước khi băm: netsh trên PC trả BSSID chữ hoa còn
        // Android trả chữ thường — cùng thiết bị phải cho CÙNG tên AP
        // (vector kiểm chứng: aa:bb:cc:dd:ee:ff -> AP_c1582e87c802).
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(bssid.trim().lowercase().toByteArray())
        return "AP_" + digest.take(6).joinToString("") { "%02x".format(it) }
    }

    /** Đổi ScanResult.timestamp (micro giây từ boot) sang epoch giây. */
    private fun scanTimestampSeconds(results: List<android.net.wifi.ScanResult>): Double {
        val maxMicros = results.maxOfOrNull { it.timestamp } ?: 0L
        val nowMs = System.currentTimeMillis()
        val elapsedMs = android.os.SystemClock.elapsedRealtime()
        return (nowMs - elapsedMs + maxMicros / 1000.0) / 1000.0
    }

    /**
     * Mở kết nối tới server. HTTPS được ghim chứng chỉ (certificate pinning);
     * HTTP (LAN do NSD tự tìm) chỉ cảnh báo trong log hệ thống — ghim không
     * áp dụng được cho HTTP vì không có chứng chỉ.
     */
    private fun openConnection(target: URL): HttpURLConnection {
        val conn = target.openConnection() as HttpURLConnection
        if (target.protocol == "https") {
            val https = conn as HttpsURLConnection
            val context = applicationContext
            // Chỉ ghi đè SSLContext khi thật sự có pin. Khi chưa điền pin, giữ
            // nguyên mặc định của Android (trust store hệ thống) — bản cũ luôn
            // ghi đè bằng TrustManager tự viết nên đã vô hiệu hoá xác thực chuỗi.
            CertificatePinner.pinnedSslContext(context)?.let { https.sslSocketFactory = it.socketFactory }
            https.hostnameVerifier = HostnameVerifier { hostname, session ->
                CertificatePinner.verifyHostname(hostname, session, context)
            }
        } else {
            android.util.Log.w("Collector", "Ket noi HTTP khong ma hoa den ${target.host} — chi dung trong mang LAN.")
        }
        return conn
    }

    private fun postJson(target: String, payload: JSONObject) {
        val isCollect = target.endsWith("/api/collect")
        val apCount = payload.optJSONObject("wifi")?.length() ?: 0
        val authToken = collectorToken.text.toString().trim()
        log("Đang gửi $apCount APs...")
        thread {
            try {
                val conn = openConnection(URL(target))
                conn.requestMethod = "POST"
                conn.connectTimeout = 6000
                conn.readTimeout = 6000
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                if (authToken.isNotEmpty()) {
                    conn.setRequestProperty("Authorization", "Bearer $authToken")
                }
                conn.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val body = stream?.bufferedReader()?.use { it.readText() } ?: ""
                conn.disconnect()
                if (code in 200..299) {
                    val json = JSONObject(body)
                    runOnUiThread { apsBadge.text = "$apCount APs" }
                    if (isCollect) showCollectAck(json) else showResult(json)
                } else {
                    log("HTTP $code: ${body.take(180)}")
                }
            } catch (e: Exception) {
                log("Network error: ${e.message}")
            }
        }
    }

    private fun hasSessionCookie(): Boolean {
        val cookieHandler = CookieHandler.getDefault() as? CookieManager ?: return false
        val base = backendUrl.text.toString().trim()
        if (!base.startsWith("http")) return false
        return try {
            cookieHandler.get(URI(base), emptyMap<String, List<String>>())
                ?.get("Cookie")?.any { it.startsWith("session=") } == true
        } catch (_: Exception) {
            false
        }
    }

    /** POST đồng bộ trả về Pair(mã HTTP, nội dung); gửi/nhận từ thread nền. */
    private fun httpPost(target: String, payload: JSONObject): Pair<Int, String> {
        var responseCode = 0
        var responseBody = ""
        try {
            val conn = openConnection(URL(target))
            conn.requestMethod = "POST"
            conn.connectTimeout = 6000
            conn.readTimeout = 6000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            conn.outputStream.use { it.write(payload.toString().toByteArray(Charsets.UTF_8)) }
            responseCode = conn.responseCode
            val stream = if (responseCode in 200..299) conn.inputStream else conn.errorStream
            responseBody = stream?.bufferedReader()?.use { it.readText() } ?: ""
            conn.disconnect()
        } catch (e: Exception) {
            responseBody = e.message ?: "network error"
        }
        return responseCode to responseBody
    }

    /** GET đồng bộ trả về Pair(mã HTTP, nội dung); gọi từ thread nền. */
    private fun httpGet(target: String): Pair<Int, String> {
        var responseCode = 0
        var responseBody = ""
        try {
            val conn = openConnection(URL(target))
            conn.requestMethod = "GET"
            conn.connectTimeout = 6000
            conn.readTimeout = 6000
            responseCode = conn.responseCode
            val stream = if (responseCode in 200..299) conn.inputStream else conn.errorStream
            responseBody = stream?.bufferedReader()?.use { it.readText() } ?: ""
            conn.disconnect()
        } catch (e: Exception) {
            responseBody = ""
        }
        return responseCode to responseBody
    }

    companion object {
        private const val PERMISSIONS_REQUEST_CODE = 100
    }
}
