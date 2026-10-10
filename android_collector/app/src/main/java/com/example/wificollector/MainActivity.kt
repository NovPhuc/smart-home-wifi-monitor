package com.example.wificollector

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
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
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import kotlin.concurrent.thread
import kotlin.math.abs

class MainActivity : AppCompatActivity(), SensorEventListener {
    private lateinit var wifiManager: WifiManager
    private lateinit var sensorManager: SensorManager
    private var accelerometer: Sensor? = null
    private lateinit var backendUrl: EditText
    private lateinit var collectorToken: EditText
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
        collectorToken.setText(prefs.getString("collectorToken", ""))
        roomName.setText(prefs.getString("roomName", ""))
        sessionId.setText(prefs.getString("sessionId", "android-session"))

        requestRuntimePermissions()

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
            .putString("collectorToken", collectorToken.text.toString().trim())
            .putString("roomName", roomName.text.toString().trim())
            .putString("sessionId", sessionId.text.toString().trim())
            .apply()
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
        if (collectorToken.text.toString().trim().isEmpty()) {
            log("Thiếu mã ghép nối. Hãy tạo mã trên dashboard của căn nhà.")
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
        val digest = MessageDigest.getInstance("SHA-256").digest(bssid.toByteArray())
        return "AP_" + digest.take(6).joinToString("") { "%02x".format(it) }
    }

    private fun postJson(target: String, payload: JSONObject) {
        val isCollect = target.endsWith("/api/collect")
        val apCount = payload.optJSONObject("wifi")?.length() ?: 0
        val authToken = collectorToken.text.toString().trim()
        log("Đang gửi $apCount APs...")
        thread {
            try {
                val conn = URL(target).openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.connectTimeout = 6000
                conn.readTimeout = 6000
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                conn.setRequestProperty("Authorization", "Bearer $authToken")
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

    companion object {
        private const val PERMISSIONS_REQUEST_CODE = 100
    }
}
