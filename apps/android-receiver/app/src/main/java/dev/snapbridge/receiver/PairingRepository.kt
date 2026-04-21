package dev.snapbridge.receiver

import android.content.Context
import java.security.SecureRandom
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.UUID
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

class PairingRepository(context: Context) {
    private val prefs = context.getSharedPreferences("snapbridge", Context.MODE_PRIVATE)
    private val json = Json { ignoreUnknownKeys = true }
    private val random = SecureRandom()
    private val lock = Any()

    val receiverId: String
        get() = synchronized(lock) {
            loadState().receiverId
        }

    val receiverName: String
        get() = synchronized(lock) {
            loadState().receiverName
        }

    val pairingCode: String
        get() = currentChallenge().pairingCode

    fun refreshPairingCode(): String {
        synchronized(lock) {
            val state = loadState()
            val nextState = state.copy(challenge = newChallenge(Instant.now()))
            saveState(nextState)
            return nextState.challenge.pairingCode
        }
    }

    fun receiverPublicKey(): String {
        return synchronized(lock) {
            loadState().publicKey
        }
    }

    fun receiverPrivateKey(): String {
        return synchronized(lock) {
            loadState().privateKey
        }
    }

    fun currentChallenge(): ReceiverChallengeState {
        synchronized(lock) {
            return refreshChallengeIfExpired(loadState()).challenge
        }
    }

    fun createPairingRequest(payload: PairingRequestPayload): PairingRequestOutcome {
        synchronized(lock) {
            val state = loadState()
            if (isExpired(state.challenge)) {
                val refreshedState = state.copy(challenge = newChallenge(Instant.now()))
                saveState(refreshedState)
                return PairingRequestOutcome.ChallengeExpired
            }
            if (payload.challenge_id != state.challenge.challengeId) {
                return PairingRequestOutcome.ChallengeMismatch
            }
            if (payload.pairing_code != state.challenge.pairingCode) {
                return PairingRequestOutcome.PairingCodeMismatch
            }

            val now = now()
            val request = PairingRequestRecord(
                requestId = UUID.randomUUID().toString(),
                challengeId = payload.challenge_id,
                senderId = payload.sender_id,
                senderName = payload.sender_name,
                senderPublicKey = payload.sender_public_key,
                verificationCode = SnapBridgeCrypto.computeSasCode(
                    localPublicKeyBase64 = state.publicKey,
                    remotePublicKeyBase64 = payload.sender_public_key,
                    challengeId = payload.challenge_id,
                ),
                status = STATUS_PENDING,
                pairId = UUID.randomUUID().toString(),
                createdAt = now,
                updatedAt = now,
            )

            val remainingRequests = state.pairingRequests.filterNot {
                it.senderId == request.senderId && it.status == STATUS_PENDING
            }
            val nextState = state.copy(
                challenge = newChallenge(Instant.now()),
                pairingRequests = trim(listOf(request) + remainingRequests, MAX_REQUESTS),
            )
            saveState(nextState)
            return PairingRequestOutcome.Accepted(request)
        }
    }

    fun getPairingRequest(requestId: String): PairingRequestRecord? {
        synchronized(lock) {
            return loadState().pairingRequests.firstOrNull { it.requestId == requestId }
        }
    }

    fun approvePairingRequest(requestId: String): PairingRequestRecord? {
        synchronized(lock) {
            val state = loadState()
            val request = state.pairingRequests.firstOrNull { it.requestId == requestId } ?: return null
            if (request.status != STATUS_PENDING) {
                return request
            }

            val approved = request.copy(
                status = STATUS_APPROVED,
                updatedAt = now(),
            )
            val pairedSender = PairedSenderRecord(
                senderId = approved.senderId,
                senderName = approved.senderName,
                senderPublicKey = approved.senderPublicKey,
                pairId = approved.pairId,
                pairedAt = approved.updatedAt,
            )
            val nextState = state.copy(
                pairingRequests = trim(
                    listOf(approved) + state.pairingRequests.filterNot { it.requestId == requestId },
                    MAX_REQUESTS,
                ),
                pairedSenders = trim(
                    listOf(pairedSender) + state.pairedSenders.filterNot { it.senderId == approved.senderId },
                    MAX_PAIRED_SENDERS,
                ),
            )
            saveState(nextState)
            return approved
        }
    }

    fun rejectPairingRequest(requestId: String, reason: String = "user_rejected"): PairingRequestRecord? {
        synchronized(lock) {
            val state = loadState()
            val request = state.pairingRequests.firstOrNull { it.requestId == requestId } ?: return null
            if (request.status != STATUS_PENDING) {
                return request
            }

            val rejected = request.copy(
                status = STATUS_REJECTED,
                reason = reason,
                updatedAt = now(),
            )
            val nextState = state.copy(
                pairingRequests = trim(
                    listOf(rejected) + state.pairingRequests.filterNot { it.requestId == requestId },
                    MAX_REQUESTS,
                ),
            )
            saveState(nextState)
            return rejected
        }
    }

    fun lookupApprovedSender(senderId: String): PairedSenderRecord? {
        synchronized(lock) {
            return loadState().pairedSenders.firstOrNull { it.senderId == senderId }
        }
    }

    fun isDuplicateMessage(messageId: String): Boolean {
        synchronized(lock) {
            return loadState().recentCaptures.any { it.messageId == messageId }
        }
    }

    fun recordSavedCapture(record: SavedCaptureRecord) {
        synchronized(lock) {
            val state = loadState()
            val nextState = state.copy(
                recentCaptures = trim(
                    listOf(record) + state.recentCaptures.filterNot { it.messageId == record.messageId },
                    MAX_RECENT_CAPTURES,
                ),
            )
            saveState(nextState)
        }
    }

    fun markServiceRunning(isRunning: Boolean, error: String? = null) {
        prefs.edit()
            .putBoolean(KEY_SERVICE_RUNNING, isRunning)
            .putString(KEY_SERVICE_ERROR, error)
            .apply()
    }

    fun markServiceStartRequested(isRequested: Boolean) {
        prefs.edit()
            .putBoolean(KEY_SERVICE_START_REQUESTED, isRequested)
            .apply()
    }

    fun shouldKeepServiceAlive(): Boolean {
        return prefs.getBoolean(KEY_SERVICE_START_REQUESTED, false)
    }

    fun dashboardState(): ReceiverDashboardState {
        synchronized(lock) {
            val state = refreshChallengeIfExpired(loadState())
            val pendingRequest = state.pairingRequests.firstOrNull { it.status == STATUS_PENDING }
            val lastCapture = state.recentCaptures.firstOrNull()
            val serviceRunning = prefs.getBoolean(KEY_SERVICE_RUNNING, false)
            val serviceError = prefs.getString(KEY_SERVICE_ERROR, null)
            val serviceRequested = shouldKeepServiceAlive()
            return ReceiverDashboardState(
                receiverName = state.receiverName,
                receiverId = state.receiverId,
                pairingCode = state.challenge.pairingCode,
                challengeExpiresAt = state.challenge.expiresAt,
                serviceRunning = serviceRunning,
                serviceError = serviceError,
                pairedSenderCount = state.pairedSenders.size,
                nextAction = when {
                    !serviceRunning && !serviceError.isNullOrBlank() ->
                        "Receiver HTTP service is not active: $serviceError. Tap restart and review Huawei background settings."
                    !serviceRunning && serviceRequested ->
                        "Receiver service is waiting to restart. Keep the foreground notification visible and allow Huawei background launch."
                    !serviceRunning ->
                        "Open the receiver screen and start the foreground receiver service."
                    pendingRequest != null ->
                        "Verify the six-digit code on both devices, then approve or reject this sender."
                    state.pairedSenders.isEmpty() ->
                        "Keep the receiver notification visible, then enter the pairing code on the Windows sender."
                    else ->
                        "Pairing is complete. Keep Huawei battery and App launch settings relaxed so screenshots can arrive in background."
                },
                pendingRequest = pendingRequest?.let {
                    PendingPairingSummary(
                        requestId = it.requestId,
                        senderName = it.senderName,
                        senderId = it.senderId,
                        verificationCode = it.verificationCode,
                        createdAt = it.createdAt,
                    )
                },
                lastCapture = lastCapture?.let {
                    LastCaptureSummary(
                        fileName = it.fileName,
                        savedUri = it.savedUri,
                        receivedAt = it.receivedAt,
                    )
                },
            )
        }
    }

    private fun refreshChallengeIfExpired(state: ReceiverState): ReceiverState {
        if (!isExpired(state.challenge)) {
            return state
        }
        val refreshed = state.copy(challenge = newChallenge(Instant.now()))
        saveState(refreshed)
        return refreshed
    }

    private fun isExpired(challenge: ReceiverChallengeState): Boolean {
        return Instant.parse(challenge.expiresAt) <= Instant.now()
    }

    private fun loadState(): ReceiverState {
        val raw = prefs.getString(KEY_STATE, null)
        if (!raw.isNullOrBlank()) {
            return json.decodeFromString(ReceiverState.serializer(), raw)
        }
        return migrateOrCreateState()
    }

    private fun saveState(state: ReceiverState) {
        prefs.edit()
            .putString(KEY_STATE, json.encodeToString(state))
            .apply()
    }

    private fun migrateOrCreateState(): ReceiverState {
        val receiverId = prefs.getString("receiver_id", null) ?: UUID.randomUUID().toString()
        val receiverName =
            prefs.getString("receiver_name", android.os.Build.MODEL ?: "Huawei Tablet") ?: "Huawei Tablet"
        val privateKey = SnapBridgeCrypto.generatePrivateKeyBase64()
        val state = ReceiverState(
            receiverId = receiverId,
            receiverName = receiverName,
            privateKey = privateKey,
            publicKey = SnapBridgeCrypto.publicKeyFromPrivateKeyBase64(privateKey),
            challenge = newChallenge(Instant.now(), prefs.getString("pairing_code", null)),
            pairingRequests = emptyList(),
            pairedSenders = emptyList(),
            recentCaptures = emptyList(),
        )
        saveState(state)
        return state
    }

    private fun newChallenge(now: Instant, pairingCode: String? = null): ReceiverChallengeState {
        return ReceiverChallengeState(
            challengeId = UUID.randomUUID().toString(),
            pairingCode = pairingCode ?: random.nextInt(1_000_000).toString().padStart(6, '0'),
            expiresAt = now.plusSeconds(CHALLENGE_TTL_SECONDS).truncatedTo(ChronoUnit.SECONDS).toString(),
        )
    }

    private fun now(): String {
        return Instant.now().truncatedTo(ChronoUnit.SECONDS).toString()
    }

    private fun <T> trim(items: List<T>, maxSize: Int): List<T> {
        return if (items.size <= maxSize) items else items.take(maxSize)
    }

    companion object {
        private const val KEY_STATE = "receiver_state"
        private const val KEY_SERVICE_RUNNING = "service_running"
        private const val KEY_SERVICE_ERROR = "service_error"
        private const val KEY_SERVICE_START_REQUESTED = "service_start_requested"
        private const val CHALLENGE_TTL_SECONDS = 300L
        private const val MAX_REQUESTS = 20
        private const val MAX_PAIRED_SENDERS = 8
        private const val MAX_RECENT_CAPTURES = 25
        const val STATUS_PENDING = "pending"
        const val STATUS_APPROVED = "approved"
        const val STATUS_REJECTED = "rejected"
    }
}

sealed class PairingRequestOutcome {
    data class Accepted(val request: PairingRequestRecord) : PairingRequestOutcome()
    object ChallengeExpired : PairingRequestOutcome()
    object ChallengeMismatch : PairingRequestOutcome()
    object PairingCodeMismatch : PairingRequestOutcome()
}
