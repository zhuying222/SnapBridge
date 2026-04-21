package dev.snapbridge.receiver

import java.security.GeneralSecurityException
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

class TransferServer(
    private val pairingRepository: PairingRepository,
    private val gallerySaver: GallerySaver,
    private val onStateChanged: (() -> Unit)? = null,
) {
    private val json = Json { explicitNulls = false; ignoreUnknownKeys = true }

    fun pairingChallengeResponse(): ApiResponse {
        val challenge = pairingRepository.currentChallenge()
        return ok(
            json.encodeToString(
                ChallengeResponse(
                    receiver_id = pairingRepository.receiverId,
                    receiver_name = pairingRepository.receiverName,
                    receiver_public_key = pairingRepository.receiverPublicKey(),
                    challenge_id = challenge.challengeId,
                    expires_at = challenge.expiresAt,
                ),
            ),
        )
    }

    fun pairingRequestResponse(payload: PairingRequestPayload): ApiResponse {
        return when (val outcome = pairingRepository.createPairingRequest(payload)) {
            PairingRequestOutcome.ChallengeExpired -> error(410, "challenge_expired")
            PairingRequestOutcome.ChallengeMismatch -> error(410, "challenge_mismatch")
            PairingRequestOutcome.PairingCodeMismatch -> error(409, "pairing_code_mismatch")
            is PairingRequestOutcome.Accepted -> {
                onStateChanged?.invoke()
                ok(
                    json.encodeToString(
                        PairingStatusResponse(
                            request_id = outcome.request.requestId,
                            status = PairingRepository.STATUS_PENDING,
                        ),
                    ),
                )
            }
        }
    }

    fun pairingStatusResponse(requestId: String): ApiResponse {
        if (requestId.isBlank()) {
            return error(400, "missing_request_id")
        }
        val request = pairingRepository.getPairingRequest(requestId) ?: return error(404, "not_found")
        return ok(json.encodeToString(request.toPairingStatusResponse()))
    }

    fun captureResponse(payload: CapturePayload): ApiResponse {
        val sender = pairingRepository.lookupApprovedSender(payload.sender_id) ?: return error(401, "unknown_sender")
        if (sender.pairId != payload.pair_id || payload.receiver_id != pairingRepository.receiverId) {
            return error(401, "pair_mismatch")
        }
        if (!payload.mime_type.startsWith("image/")) {
            return error(400, "unsupported_mime_type")
        }
        if (pairingRepository.isDuplicateMessage(payload.message_id)) {
            return error(409, "duplicate_message_id")
        }

        val metadata = mapOf<String, Any>(
            "pair_id" to payload.pair_id,
            "sender_id" to payload.sender_id,
            "receiver_id" to payload.receiver_id,
            "message_id" to payload.message_id,
            "captured_at" to payload.captured_at,
            "mime_type" to payload.mime_type,
            "file_name" to payload.file_name,
            "width" to payload.width,
            "height" to payload.height,
            "sha256" to payload.sha256,
        )

        return try {
            val transferKey = SnapBridgeCrypto.deriveTransferKey(
                privateKeyBase64 = pairingRepository.receiverPrivateKey(),
                remotePublicKeyBase64 = sender.senderPublicKey,
                pairId = payload.pair_id,
            )
            val plaintext = SnapBridgeCrypto.decryptPayload(
                transferKey = transferKey,
                metadata = metadata,
                nonceBase64 = payload.nonce,
                ciphertextBase64 = payload.ciphertext,
            )
            val receivedSha256 = SnapBridgeCrypto.sha256Hex(plaintext)
            if (receivedSha256 != payload.sha256) {
                return error(400, "hash_mismatch")
            }

            val savedUri = gallerySaver.saveImage(
                fileName = payload.file_name,
                mimeType = payload.mime_type,
                bytes = plaintext,
            )
            pairingRepository.recordSavedCapture(
                SavedCaptureRecord(
                    messageId = payload.message_id,
                    senderId = payload.sender_id,
                    fileName = payload.file_name,
                    mimeType = payload.mime_type,
                    receivedSha256 = receivedSha256,
                    savedUri = savedUri,
                    receivedAt = payload.captured_at,
                ),
            )

            val ackPayload = linkedMapOf<String, Any>(
                "message_id" to payload.message_id,
                "status" to "saved",
                "received_sha256" to receivedSha256,
                "saved_uri" to savedUri,
            )
            onStateChanged?.invoke()
            ok(
                json.encodeToString(
                    CaptureAckResponse(
                        message_id = payload.message_id,
                        status = "saved",
                        received_sha256 = receivedSha256,
                        saved_uri = savedUri,
                        ack_signature = SnapBridgeCrypto.computeAckSignature(transferKey, ackPayload),
                    ),
                ),
            )
        } catch (_: IllegalArgumentException) {
            error(400, "invalid_encoding")
        } catch (_: GeneralSecurityException) {
            error(401, "invalid_crypto")
        } catch (exception: IllegalStateException) {
            error(500, "save_failed", exception.message.orEmpty())
        }
    }

    fun badJsonResponse(): ApiResponse {
        return error(400, "invalid_json")
    }

    private fun PairingRequestRecord.toPairingStatusResponse(): PairingStatusResponse {
        return PairingStatusResponse(
            request_id = requestId,
            status = status,
            pair_id = if (status == PairingRepository.STATUS_APPROVED) pairId else null,
            receiver_id = if (status == PairingRepository.STATUS_APPROVED) pairingRepository.receiverId else null,
            receiver_name = if (status == PairingRepository.STATUS_APPROVED) pairingRepository.receiverName else null,
            receiver_public_key =
                if (status == PairingRepository.STATUS_APPROVED) pairingRepository.receiverPublicKey() else null,
            reason = reason,
        )
    }

    private fun ok(body: String): ApiResponse {
        return ApiResponse(200, body)
    }

    private fun error(statusCode: Int, reason: String, note: String? = null): ApiResponse {
        val body = buildJsonObject {
            put("reason", reason)
            if (!note.isNullOrBlank()) {
                put("note", note)
            }
        }
        return ApiResponse(statusCode, json.encodeToString(body))
    }
}

data class ApiResponse(
    val statusCode: Int,
    val body: String,
)
