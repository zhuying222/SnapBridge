package dev.snapbridge.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (action !in START_ACTIONS) {
            return
        }

        val repository = PairingRepository(context)
        if (!repository.shouldKeepServiceAlive()) {
            Log.i(TAG, "Skipping receiver service auto-start for action=$action because it is not armed")
            return
        }

        Log.i(TAG, "Starting receiver service after action=$action")
        ReceiverService.ensureRunning(context)
    }

    companion object {
        private const val TAG = "SnapBridgeBoot"
        private val START_ACTIONS = setOf(
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED,
            "android.intent.action.QUICKBOOT_POWERON",
        )
    }
}
