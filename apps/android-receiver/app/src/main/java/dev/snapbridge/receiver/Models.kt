package dev.snapbridge.receiver

import kotlinx.serialization.Serializable

@Serializable
data class ChallengeResponse(
    val receiver_id: String,
    val receiver_name: String,
    val receiver_public_key: String,
    val challenge_id: String,
    val expires_at: String,
)

@Serializable
data class PairingRequestPayload(
    val sender_id: String,
    val sender_name: String,
    val sender_public_key: String,
    val challenge_id: String,
    val pairing_code: String,
)

@Serializable
data class PairingStatusResponse(
    val request_id: String,
    val status: String,
    val pair_id: String? = null,
    val receiver_id: String? = null,
    val receiver_name: String? = null,
    val receiver_public_key: String? = null,
    val reason: String? = null,
)

@Serializable
data class CapturePayload(
    val pair_id: String,
    val sender_id: String,
    val receiver_id: String,
    val message_id: String,
    val captured_at: String,
    val mime_type: String,
    val file_name: String,
    val width: Int,
    val height: Int,
    val sha256: String,
    val nonce: String,
    val ciphertext: String,
)

@Serializable
data class CaptureAckResponse(
    val message_id: String,
    val status: String,
    val received_sha256: String,
    val saved_uri: String,
    val ack_signature: String,
)

@Serializable
data class ReceiverState(
    val receiverId: String,
    val receiverName: String,
    val privateKey: String,
    val publicKey: String,
    val challenge: ReceiverChallengeState,
    val pairingRequests: List<PairingRequestRecord>,
    val pairedSenders: List<PairedSenderRecord>,
    val recentCaptures: List<SavedCaptureRecord>,
)

@Serializable
data class ReceiverChallengeState(
    val challengeId: String,
    val pairingCode: String,
    val expiresAt: String,
)

@Serializable
data class PairingRequestRecord(
    val requestId: String,
    val challengeId: String,
    val senderId: String,
    val senderName: String,
    val senderPublicKey: String,
    val verificationCode: String,
    val status: String,
    val pairId: String,
    val reason: String? = null,
    val createdAt: String,
    val updatedAt: String,
)

@Serializable
data class PairedSenderRecord(
    val senderId: String,
    val senderName: String,
    val senderPublicKey: String,
    val pairId: String,
    val pairedAt: String,
)

@Serializable
data class SavedCaptureRecord(
    val messageId: String,
    val senderId: String,
    val fileName: String,
    val mimeType: String,
    val receivedSha256: String,
    val savedUri: String,
    val receivedAt: String,
)

data class ReceiverDashboardState(
    val receiverName: String,
    val receiverId: String,
    val pairingCode: String,
    val challengeExpiresAt: String,
    val serviceRunning: Boolean,
    val pairedSenderCount: Int,
    val nextAction: String,
    val pendingRequest: PendingPairingSummary?,
    val lastCapture: LastCaptureSummary?,
)

data class PendingPairingSummary(
    val requestId: String,
    val senderName: String,
    val senderId: String,
    val verificationCode: String,
    val createdAt: String,
)

data class LastCaptureSummary(
    val fileName: String,
    val savedUri: String,
    val receivedAt: String,
)
