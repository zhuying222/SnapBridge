package dev.snapbridge.receiver

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import dev.snapbridge.receiver.databinding.ActivityMainBinding
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var repository: PairingRepository
    private val formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss").withZone(ZoneId.systemDefault())
    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) {
            render()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        repository = PairingRepository(this)

        binding.refreshPairingCode.setOnClickListener {
            repository.refreshPairingCode()
            ReceiverService.requestNotificationRefresh(this)
            render()
        }
        binding.approvePairing.setOnClickListener {
            val requestId = binding.approvePairing.tag as? String ?: return@setOnClickListener
            repository.approvePairingRequest(requestId)
            ReceiverService.requestNotificationRefresh(this)
            render()
        }
        binding.rejectPairing.setOnClickListener {
            val requestId = binding.rejectPairing.tag as? String ?: return@setOnClickListener
            repository.rejectPairingRequest(requestId)
            ReceiverService.requestNotificationRefresh(this)
            render()
        }
        binding.restartReceiverService.setOnClickListener {
            ReceiverService.restartHttpServer(this)
            render()
        }
        binding.notificationPermissionAction.setOnClickListener {
            handleNotificationAction()
        }
        binding.batteryOptimizationAction.setOnClickListener {
            if (!BackgroundSetupNavigator.requestIgnoreBatteryOptimizations(this)) {
                BackgroundSetupNavigator.openBatteryOptimizationSettings(this)
            }
        }
        binding.vendorBackgroundSettings.setOnClickListener {
            val backgroundReadiness = BackgroundSetupNavigator.readStatus(this)
            if (backgroundReadiness.isHuaweiFamily) {
                BackgroundSetupNavigator.openHuaweiBackgroundSettings(this)
            } else {
                BackgroundSetupNavigator.openBatteryOptimizationSettings(this)
            }
        }
        binding.openAppSettings.setOnClickListener {
            BackgroundSetupNavigator.openAppDetailsSettings(this)
        }

        ReceiverService.ensureRunning(this)
        render()
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    private fun render() {
        val dashboard = repository.dashboardState()
        val backgroundReadiness = BackgroundSetupNavigator.readStatus(this)

        binding.receiverName.text = dashboard.receiverName
        binding.receiverId.text = dashboard.receiverId
        binding.serviceStatus.text =
            if (dashboard.serviceRunning) {
                "Running on port ${ReceiverService.PORT}"
            } else {
                dashboard.serviceError?.let { "Stopped: $it" } ?: "Stopped"
            }
        binding.backgroundStatus.text = backgroundReadiness.summaryText
        binding.backgroundInstructions.text = backgroundReadiness.instructionsText
        binding.notificationPermissionAction.visibility =
            if (!backgroundReadiness.notificationsEnabled || backgroundReadiness.canRequestNotificationPermission) {
                View.VISIBLE
            } else {
                View.GONE
            }
        binding.notificationPermissionAction.text =
            if (backgroundReadiness.canRequestNotificationPermission) {
                "Allow Notifications"
            } else {
                "Open Notification Settings"
            }
        binding.batteryOptimizationAction.visibility =
            if (backgroundReadiness.batteryOptimizationIgnored) {
                View.GONE
            } else {
                View.VISIBLE
            }
        binding.vendorBackgroundSettings.text =
            if (backgroundReadiness.isHuaweiFamily) {
                "Open Huawei Phone Manager"
            } else {
                "Open Battery Settings"
            }
        binding.nextAction.text = dashboard.nextAction
        binding.pairingCode.text = dashboard.pairingCode
        binding.challengeExpiresAt.text = formatTimestamp(dashboard.challengeExpiresAt)
        binding.pairedSenders.text = dashboard.pairedSenderCount.toString()

        val pending = dashboard.pendingRequest
        binding.pendingRequestContainer.visibility = if (pending != null) View.VISIBLE else View.GONE
        if (pending != null) {
            binding.pendingSender.text = "${pending.senderName} (${pending.senderId})"
            binding.pendingRequestId.text = pending.requestId
            binding.verificationCode.text = pending.verificationCode
            binding.pendingCreatedAt.text = formatTimestamp(pending.createdAt)
            binding.approvePairing.tag = pending.requestId
            binding.rejectPairing.tag = pending.requestId
        } else {
            binding.pendingSender.text = "No pending pairing requests"
            binding.pendingRequestId.text = "-"
            binding.verificationCode.text = "-"
            binding.pendingCreatedAt.text = "-"
            binding.approvePairing.tag = null
            binding.rejectPairing.tag = null
        }

        val lastCapture = dashboard.lastCapture
        binding.lastCapture.text = if (lastCapture == null) {
            "No screenshots have been saved yet."
        } else {
            "${lastCapture.fileName}\n${lastCapture.savedUri}\n${formatTimestamp(lastCapture.receivedAt)}"
        }
    }

    private fun handleNotificationAction() {
        if (
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            return
        }
        BackgroundSetupNavigator.openNotificationSettings(this)
    }

    private fun formatTimestamp(value: String): String {
        return runCatching { formatter.format(Instant.parse(value)) }.getOrDefault(value)
    }
}
