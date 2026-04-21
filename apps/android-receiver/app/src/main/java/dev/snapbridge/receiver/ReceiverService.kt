package dev.snapbridge.receiver

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import android.util.Log
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat

class ReceiverService : Service() {
    private lateinit var gallerySaver: GallerySaver
    private var server: ReceiverHttpServer? = null
    private lateinit var pairingRepository: PairingRepository
    private lateinit var notificationManager: NotificationManager

    override fun onCreate() {
        super.onCreate()
        pairingRepository = PairingRepository(this)
        gallerySaver = GallerySaver(this)
        notificationManager = getSystemService(NotificationManager::class.java)
        createChannelIfNeeded()
        cancelScheduledRestart()
        pairingRepository.markServiceStartRequested(true)
        pairingRepository.markServiceRunning(false)
        startInForeground()
        startHttpServer()
        updateNotification()
    }

    override fun onDestroy() {
        pairingRepository.markServiceRunning(false)
        server?.stop()
        server = null
        scheduleRestart("service_destroyed")
        super.onDestroy()
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        scheduleRestart("task_removed")
        super.onTaskRemoved(rootIntent)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        pairingRepository.markServiceStartRequested(true)
        cancelScheduledRestart()
        when (intent?.action) {
            ACTION_RESTART_HTTP_SERVER -> restartHttpServer()
            ACTION_REFRESH_NOTIFICATION -> updateNotification()
            else -> {
                if (server == null) {
                    startHttpServer()
                }
                updateNotification()
            }
        }
        return START_STICKY
    }

    private fun startInForeground() {
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification(),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE,
        )
    }

    private fun startHttpServer() {
        try {
            server = ReceiverHttpServer(
                transferServer = TransferServer(pairingRepository, gallerySaver) {
                    updateNotification()
                },
                port = PORT,
            )
            server?.start(SOCKET_READ_TIMEOUT_MS, false)
            pairingRepository.markServiceRunning(isRunning = true, error = null)
        } catch (exception: Exception) {
            Log.e(TAG, "Failed to start receiver HTTP server", exception)
            pairingRepository.markServiceRunning(
                isRunning = false,
                error = "${exception.javaClass.simpleName}: ${exception.message.orEmpty()}".trim(),
            )
        }
    }

    private fun restartHttpServer() {
        server?.stop()
        server = null
        pairingRepository.markServiceRunning(false)
        startHttpServer()
        updateNotification()
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
        val builder = Notification.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("SnapBridge receiver")
            .setContentText(contentText)
            .setSmallIcon(android.R.drawable.stat_sys_upload_done)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setShowWhen(false)
            .setContentIntent(
                PendingIntent.getActivity(
                    this,
                    0,
                    Intent(this, MainActivity::class.java),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                ),
            )
            .setStyle(Notification.BigTextStyle().bigText(contentText))
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            builder.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE)
        }
        return builder.build()
    }

    private fun createChannelIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return
        }
        notificationManager.createNotificationChannel(
            NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "SnapBridge Receiver",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "Foreground receiver status for SnapBridge background transfers"
            },
        )
    }

    private fun updateNotification() {
        notificationManager.notify(NOTIFICATION_ID, buildNotification())
    }

    private fun scheduleRestart(reason: String) {
        if (!pairingRepository.shouldKeepServiceAlive()) {
            return
        }
        val alarmManager = getSystemService(AlarmManager::class.java) ?: return
        val pendingIntent = restartPendingIntent()
        val triggerAt = SystemClock.elapsedRealtime() + SERVICE_RESTART_DELAY_MS
        cancelScheduledRestart()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            alarmManager.setAndAllowWhileIdle(AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt, pendingIntent)
        } else {
            alarmManager.set(AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt, pendingIntent)
        }
        pairingRepository.markServiceRunning(false, "Waiting for service restart ($reason)")
        Log.w(TAG, "Scheduled receiver service restart after $reason")
    }

    private fun cancelScheduledRestart() {
        val alarmManager = getSystemService(AlarmManager::class.java) ?: return
        alarmManager.cancel(restartPendingIntent())
    }

    private fun restartPendingIntent(): PendingIntent {
        return PendingIntent.getBroadcast(
            this,
            RESTART_REQUEST_CODE,
            Intent(this, ServiceRestartReceiver::class.java).setAction(ServiceRestartReceiver.ACTION_RESTART_SERVICE),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    companion object {
        private const val TAG = "SnapBridgeReceiver"
        private const val NOTIFICATION_CHANNEL_ID = "snapbridge"
        private const val NOTIFICATION_ID = 1001
        private const val ACTION_REFRESH_NOTIFICATION = "dev.snapbridge.receiver.action.REFRESH_NOTIFICATION"
        private const val ACTION_ENSURE_RUNNING = "dev.snapbridge.receiver.action.ENSURE_RUNNING"
        private const val ACTION_RESTART_HTTP_SERVER = "dev.snapbridge.receiver.action.RESTART_HTTP_SERVER"
        private const val SOCKET_READ_TIMEOUT_MS = 5000
        private const val SERVICE_RESTART_DELAY_MS = 2_000L
        private const val RESTART_REQUEST_CODE = 2001
        const val PORT = 8765

        fun ensureRunning(context: Context) {
            val repository = PairingRepository(context)
            repository.markServiceStartRequested(true)
            val intent = Intent(context, ReceiverService::class.java).setAction(ACTION_ENSURE_RUNNING)
            runCatching {
                ContextCompat.startForegroundService(context, intent)
            }.onFailure { exception ->
                Log.e(TAG, "Failed to start receiver foreground service", exception)
                repository.markServiceRunning(
                    isRunning = false,
                    error = "Foreground service start blocked: ${exception.javaClass.simpleName}",
                )
            }
        }

        fun restartHttpServer(context: Context) {
            val repository = PairingRepository(context)
            repository.markServiceStartRequested(true)
            val intent = Intent(context, ReceiverService::class.java).setAction(ACTION_RESTART_HTTP_SERVER)
            runCatching {
                ContextCompat.startForegroundService(context, intent)
            }.onFailure { exception ->
                Log.e(TAG, "Failed to restart receiver HTTP server", exception)
                repository.markServiceRunning(
                    isRunning = false,
                    error = "Receiver restart blocked: ${exception.javaClass.simpleName}",
                )
            }
        }

        fun requestNotificationRefresh(context: Context) {
            val intent = Intent(context, ReceiverService::class.java).setAction(ACTION_REFRESH_NOTIFICATION)
            runCatching {
                ContextCompat.startForegroundService(context, intent)
            }.onFailure { exception ->
                Log.w(TAG, "Failed to refresh receiver notification", exception)
            }
        }
    }
}
