package dev.snapbridge.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

class ServiceRestartReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != ACTION_RESTART_SERVICE) {
            return
        }

        val repository = PairingRepository(context)
        if (!repository.shouldKeepServiceAlive()) {
            Log.i(TAG, "Skipping scheduled receiver restart because it is not armed")
            return
        }

        Log.i(TAG, "Restarting receiver service from alarm")
        ReceiverService.ensureRunning(context)
    }

    companion object {
        const val ACTION_RESTART_SERVICE = "dev.snapbridge.receiver.action.RESTART_SERVICE"

        private const val TAG = "SnapBridgeRestart"
    }
}
