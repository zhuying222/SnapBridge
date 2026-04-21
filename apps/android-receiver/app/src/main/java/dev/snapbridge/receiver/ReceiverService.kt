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
import androidx.core.content.ContextCompat
import io.ktor.server.cio.CIO
import io.ktor.server.engine.embeddedServer

class ReceiverService : Service() {
    private var server = null as io.ktor.server.engine.ApplicationEngine?
    private lateinit var pairingRepository: PairingRepository
    private lateinit var notificationManager: NotificationManager

    override fun onCreate() {
        super.onCreate()
        pairingRepository = PairingRepository(this)
        val gallerySaver = GallerySaver(this)
        notificationManager = getSystemService(NotificationManager::class.java)
        createChannelIfNeeded()
        pairingRepository.markServiceRunning(true)
        startForeground(NOTIFICATION_ID, buildNotification())
        server = embeddedServer(CIO, host = "0.0.0.0", port = 8765) {
            TransferServer(pairingRepository, gallerySaver) {
                updateNotification()
            }.installRoutes()
        }.start(wait = false)
        updateNotification()
    }

    override fun onDestroy() {
        pairingRepository.markServiceRunning(false)
        server?.stop(1000, 2000)
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
        private const val NOTIFICATION_ID = 1001
        private const val ACTION_REFRESH_NOTIFICATION = "dev.snapbridge.receiver.action.REFRESH_NOTIFICATION"
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
