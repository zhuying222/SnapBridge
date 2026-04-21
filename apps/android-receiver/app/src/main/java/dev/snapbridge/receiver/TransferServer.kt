package dev.snapbridge.receiver

import io.ktor.http.HttpStatusCode
import io.ktor.serialization.kotlinx.json.json
import io.ktor.server.application.Application
import io.ktor.server.application.call
import io.ktor.server.plugins.contentnegotiation.ContentNegotiation
import io.ktor.server.request.receive
import io.ktor.server.response.respond
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.server.routing.routing
import java.security.GeneralSecurityException

class TransferServer(
    private val pairingRepository: PairingRepository,
    private val gallerySaver: GallerySaver,
    private val onStateChanged: (() -> Unit)? = null,
) {
    fun Application.installRoutes() {
        install(ContentNegotiation) {
            json()
        }

        routing {
            get("/api/v1/pairing/challenge") {
                val challenge = pairingRepository.currentChallenge()
                call.respond(
                    ChallengeResponse(
                        receiver_id = pairingRepository.receiverId,
                        receiver_name = pairingRepository.receiverName,
                        receiver_public_key = pairingRepository.receiverPublicKey(),
                        challenge_id = challenge.challengeId,
                        expires_at = challenge.expiresAt,
                    ),
                )
            }

            post("/api/v1/pairing/requests") {
                val payload = call.receive<PairingRequestPayload>()
                when (val outcome = pairingRepository.createPairingRequest(payload)) {
                    PairingRequestOutcome.ChallengeExpired -> {
                        call.respond(HttpStatusCode.Gone, mapOf("reason" to "challenge_expired"))
                    }
                    PairingRequestOutcome.ChallengeMismatch -> {
                        call.respond(HttpStatusCode.Gone, mapOf("reason" to "challenge_mismatch"))
                    }
                    PairingRequestOutcome.PairingCodeMismatch -> {
                        call.respond(HttpStatusCode.Conflict, mapOf("reason" to "pairing_code_mismatch"))
                    }
                    is PairingRequestOutcome.Accepted -> {
                        onStateChanged?.invoke()
                        call.respond(
                            PairingStatusResponse(
                                request_id = outcome.request.requestId,
                                status = PairingRepository.STATUS_PENDING,
                            ),
                        )
                    }
                }
            }

            get("/api/v1/pairing/requests/{request_id}") {
                val requestId = call.parameters["request_id"]
                if (requestId.isNullOrBlank()) {
                    call.respond(HttpStatusCode.BadRequest, mapOf("reason" to "missing_request_id"))
                    return@get
                }
                val request = pairingRepository.getPairingRequest(requestId)
                if (request == null) {
                    call.respond(HttpStatusCode.NotFound, mapOf("reason" to "not_found"))
                    return@get
                }
                call.respond(request.toPairingStatusResponse())
            }

            post("/api/v1/captures") {
                val payload = call.receive<CapturePayload>()
                val sender = pairingRepository.lookupApprovedSender(payload.sender_id)
                if (sender == null) {
                    call.respond(HttpStatusCode.Unauthorized, mapOf("reason" to "unknown_sender"))
                    return@post
                }
                if (sender.pairId != payload.pair_id || payload.receiver_id != pairingRepository.receiverId) {
                    call.respond(HttpStatusCode.Unauthorized, mapOf("reason" to "pair_mismatch"))
                    return@post
                }
                if (!payload.mime_type.startsWith("image/")) {
                    call.respond(HttpStatusCode.BadRequest, mapOf("reason" to "unsupported_mime_type"))
                    return@post
                }
                if (pairingRepository.isDuplicateMessage(payload.message_id)) {
                    call.respond(HttpStatusCode.Conflict, mapOf("reason" to "duplicate_message_id"))
                    return@post
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

                try {
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
                        call.respond(HttpStatusCode.BadRequest, mapOf("reason" to "hash_mismatch"))
                        return@post
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
                    call.respond(
                        CaptureAckResponse(
                            message_id = payload.message_id,
                            status = "saved",
                            received_sha256 = receivedSha256,
                            saved_uri = savedUri,
                            ack_signature = SnapBridgeCrypto.computeAckSignature(transferKey, ackPayload),
                        ),
                    )
                } catch (_: IllegalArgumentException) {
                    call.respond(HttpStatusCode.BadRequest, mapOf("reason" to "invalid_encoding"))
                } catch (_: GeneralSecurityException) {
                    call.respond(HttpStatusCode.Unauthorized, mapOf("reason" to "invalid_crypto"))
                } catch (exception: IllegalStateException) {
                    call.respond(
                        HttpStatusCode.InternalServerError,
                        mapOf(
                            "reason" to "save_failed",
                            "note" to exception.message.orEmpty(),
                        ),
                    )
                }
            }
        }
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
}
