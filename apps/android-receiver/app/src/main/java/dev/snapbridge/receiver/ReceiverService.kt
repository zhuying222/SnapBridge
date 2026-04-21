package dev.snapbridge.receiver

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.content.ContextCompat

class ReceiverService : Service() {
    private var server: ReceiverHttpServer? = null
    private lateinit var pairingRepository: PairingRepository
    private lateinit var notificationManager: NotificationManager

    override fun onCreate() {
        super.onCreate()
        pairingRepository = PairingRepository(this)
        val gallerySaver = GallerySaver(this)
        notificationManager = getSystemService(NotificationManager::class.java)
        createChannelIfNeeded()
        pairingRepository.markServiceRunning(false)
        startForeground(NOTIFICATION_ID, buildNotification())
        try {
            server = ReceiverHttpServer(
                transferServer = TransferServer(pairingRepository, gallerySaver) {
                    updateNotification()
                },
                port = PORT,
            )
            server?.start(SOCKET_READ_TIMEOUT_MS, false)
            pairingRepository.markServiceRunning(true)
        } catch (exception: Exception) {
            Log.e(TAG, "Failed to start receiver HTTP server", exception)
            pairingRepository.markServiceRunning(
                isRunning = false,
                error = "${exception.javaClass.simpleName}: ${exception.message.orEmpty()}".trim(),
            )
        }
        updateNotification()
    }

    override fun onDestroy() {
        pairingRepository.markServiceRunning(false)
        server?.stop()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_REFRESH_NOTIFICATION) {
            updateNotification()
        }
        return START_STICKY
    }

    private fun buildNotification(): Notification {
        val dashboard = pairingRepository.dashboardState()
        val contentText = when {
            !dashboard.serviceRunning && !dashboard.serviceError.isNullOrBlank() ->
                "Receiver stopped: ${dashboard.serviceError}"
            !dashboard.serviceRunning ->
                "Starting receiver on port $PORT"
            dashboard.pendingRequest != null ->
                "Pending pairing: ${dashboard.pendingRequest.senderName} (${dashboard.pendingRequest.verificationCode})"
            dashboard.lastCapture != null ->
                "Listening on port $PORT. Last save: ${dashboard.lastCapture.fileName}"
            else ->
                "Listening on port $PORT for screenshots and pairing requests"
        }
        return Notification.Builder(this, "snapbridge")
            .setContentTitle("SnapBridge receiver")
            .setContentText(contentText)
            .setSmallIcon(android.R.drawable.stat_sys_upload_done)
            .setContentIntent(
                PendingIntent.getActivity(
                    this,
                    0,
                    Intent(this, MainActivity::class.java),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                ),
            )
            .build()
    }

    private fun createChannelIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return
        }
        notificationManager.createNotificationChannel(
            NotificationChannel(
                "snapbridge",
                "SnapBridge Receiver",
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
    }

    private fun updateNotification() {
        notificationManager.notify(NOTIFICATION_ID, buildNotification())
    }

    companion object {
        private const val TAG = "SnapBridgeReceiver"
        private const val NOTIFICATION_ID = 1001
        private const val ACTION_REFRESH_NOTIFICATION = "dev.snapbridge.receiver.action.REFRESH_NOTIFICATION"
        private const val SOCKET_READ_TIMEOUT_MS = 5000
        const val PORT = 8765

        fun ensureRunning(context: Context) {
            ContextCompat.startForegroundService(context, Intent(context, ReceiverService::class.java))
        }

        fun requestNotificationRefresh(context: Context) {
            val intent = Intent(context, ReceiverService::class.java).setAction(ACTION_REFRESH_NOTIFICATION)
            ContextCompat.startForegroundService(context, intent)
        }
    }
}
