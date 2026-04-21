package dev.snapbridge.receiver

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import java.util.Locale

data class BackgroundReadiness(
    val notificationsEnabled: Boolean,
    val canRequestNotificationPermission: Boolean,
    val batteryOptimizationIgnored: Boolean,
    val isHuaweiFamily: Boolean,
) {
    val summaryText: String
        get() = buildString {
            append("Notifications: ")
            append(if (notificationsEnabled) "allowed" else "blocked")
            append('\n')
            append("Battery optimization: ")
            append(if (batteryOptimizationIgnored) "unrestricted" else "still managed by the system")
            append('\n')
            append(
                if (isHuaweiFamily) {
                    "Huawei App launch: review manual background launch settings"
                } else {
                    "Background checklist: keep the foreground receiver notification visible"
                },
            )
        }

    val instructionsText: String
        get() = if (isHuaweiFamily) {
            "Huawei checklist:\n" +
                "1. Open Phone Manager and find App launch.\n" +
                "2. Disable Manage automatically for SnapBridge Receiver.\n" +
                "3. Enable Auto-launch, Secondary launch, and Run in background.\n" +
                "4. Keep the receiver notification visible, and lock the app in recent tasks if the tablet supports it.\n" +
                "5. If transfers still stop after the app is minimized, remove battery optimization for this app in Android Settings."
        } else {
            "Background checklist:\n" +
                "1. Keep the receiver foreground notification visible.\n" +
                "2. Allow app notifications so service state stays visible.\n" +
                "3. Remove battery optimization for this app if transfers stop while it is in background.\n" +
                "4. Reopen the app and tap restart if the receiver service stops."
        }
}

object BackgroundSetupNavigator {
    fun readStatus(context: Context): BackgroundReadiness {
        val notificationsEnabled = NotificationManagerCompat.from(context).areNotificationsEnabled()
        val canRequestNotificationPermission =
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
                PackageManager.PERMISSION_GRANTED
        val batteryOptimizationIgnored = context.getSystemService(PowerManager::class.java)
            ?.isIgnoringBatteryOptimizations(context.packageName)
            ?: true
        return BackgroundReadiness(
            notificationsEnabled = notificationsEnabled,
            canRequestNotificationPermission = canRequestNotificationPermission,
            batteryOptimizationIgnored = batteryOptimizationIgnored,
            isHuaweiFamily = isHuaweiFamily(),
        )
    }

    fun requestIgnoreBatteryOptimizations(context: Context): Boolean {
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
            data = Uri.parse("package:${context.packageName}")
        }
        return launch(context, intent)
    }

    fun openBatteryOptimizationSettings(context: Context): Boolean {
        return launch(context, Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) ||
            openAppDetailsSettings(context)
    }

    fun openNotificationSettings(context: Context): Boolean {
        val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).apply {
            putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
        }
        return launch(context, intent) || openAppDetailsSettings(context)
    }

    fun openHuaweiBackgroundSettings(context: Context): Boolean {
        val launchIntent = context.packageManager.getLaunchIntentForPackage(HUAWEI_SYSTEM_MANAGER_PACKAGE)
        if (launchIntent != null && launch(context, launchIntent)) {
            return true
        }
        return openBatteryOptimizationSettings(context)
    }

    fun openAppDetailsSettings(context: Context): Boolean {
        val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
            data = Uri.parse("package:${context.packageName}")
        }
        return launch(context, intent)
    }

    private fun launch(context: Context, intent: Intent): Boolean {
        val launchIntent = Intent(intent).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (launchIntent.resolveActivity(context.packageManager) == null) {
            return false
        }
        return runCatching {
            context.startActivity(launchIntent)
            true
        }.getOrDefault(false)
    }

    private fun isHuaweiFamily(): Boolean {
        return sequenceOf(Build.MANUFACTURER, Build.BRAND)
            .filterNotNull()
            .map { it.uppercase(Locale.ROOT) }
            .any { it.contains("HUAWEI") || it.contains("HONOR") }
    }

    private const val HUAWEI_SYSTEM_MANAGER_PACKAGE = "com.huawei.systemmanager"
}
