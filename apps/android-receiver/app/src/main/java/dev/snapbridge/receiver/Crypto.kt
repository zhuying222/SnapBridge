package dev.snapbridge.receiver

import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import org.bouncycastle.crypto.agreement.X25519Agreement
import org.bouncycastle.crypto.digests.SHA256Digest
import org.bouncycastle.crypto.generators.HKDFBytesGenerator
import org.bouncycastle.crypto.params.HKDFParameters
import org.bouncycastle.crypto.params.X25519PrivateKeyParameters
import org.bouncycastle.crypto.params.X25519PublicKeyParameters

object SnapBridgeCrypto {
    private const val TRANSFER_INFO = "snapbridge-transfer-v1"
    private val secureRandom = SecureRandom()
    private val json = Json

    fun generatePrivateKeyBase64(): String {
        val privateKey = X25519PrivateKeyParameters(secureRandom)
        return base64Encode(privateKey.encoded)
    }

    fun publicKeyFromPrivateKeyBase64(privateKeyBase64: String): String {
        val privateKeyBytes = base64Decode(privateKeyBase64)
        val privateKey = X25519PrivateKeyParameters(privateKeyBytes, 0)
        return base64Encode(privateKey.generatePublicKey().encoded)
    }

    fun computeSasCode(
        localPublicKeyBase64: String,
        remotePublicKeyBase64: String,
        challengeId: String,
    ): String {
        val keys = listOf(
            base64Decode(localPublicKeyBase64),
            base64Decode(remotePublicKeyBase64),
        ).sortedWith(::compareByteArrays)
        val digest = sha256(
            challengeId.toByteArray(StandardCharsets.UTF_8) + keys[0] + keys[1],
        )
        val value = (
            ((digest[0].toInt() and 0xff) shl 24) or
                ((digest[1].toInt() and 0xff) shl 16) or
                ((digest[2].toInt() and 0xff) shl 8) or
                (digest[3].toInt() and 0xff)
            ) % 1_000_000
        return value.toString().padStart(6, '0')
    }

    fun deriveTransferKey(
        privateKeyBase64: String,
        remotePublicKeyBase64: String,
        pairId: String,
    ): ByteArray {
        val privateKey = X25519PrivateKeyParameters(base64Decode(privateKeyBase64), 0)
        val remotePublicKey = X25519PublicKeyParameters(base64Decode(remotePublicKeyBase64), 0)
        val sharedSecret = ByteArray(32)
        X25519Agreement().apply {
            init(privateKey)
            calculateAgreement(remotePublicKey, sharedSecret, 0)
        }

        val output = ByteArray(32)
        val hkdf = HKDFBytesGenerator(SHA256Digest())
        hkdf.init(
            HKDFParameters(
                sharedSecret,
                sha256(pairId.toByteArray(StandardCharsets.UTF_8)),
                TRANSFER_INFO.toByteArray(StandardCharsets.UTF_8),
            ),
        )
        hkdf.generateBytes(output, 0, output.size)
        return output
    }

    fun decryptPayload(
        transferKey: ByteArray,
        metadata: Map<String, Any>,
        nonceBase64: String,
        ciphertextBase64: String,
    ): ByteArray {
        // TODO: Verify this path end-to-end against the Windows sender from Android Studio.
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(
            Cipher.DECRYPT_MODE,
            SecretKeySpec(transferKey, "AES"),
            GCMParameterSpec(128, base64Decode(nonceBase64)),
        )
        cipher.updateAAD(canonicalJson(metadata))
        return cipher.doFinal(base64Decode(ciphertextBase64))
    }

    fun computeAckSignature(transferKey: ByteArray, ackPayload: Map<String, Any>): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(transferKey, "HmacSHA256"))
        return base64Encode(mac.doFinal(canonicalJson(ackPayload)))
    }

    fun sha256Hex(data: ByteArray): String {
        return sha256(data).joinToString(separator = "") { "%02x".format(it) }
    }

    fun canonicalJson(data: Map<String, Any>): ByteArray {
        val jsonObject = buildJsonObject {
            data.toSortedMap().forEach { (key, value) ->
                put(key, value.toJsonElement())
            }
        }
        return json.encodeToString(JsonObject.serializer(), jsonObject).toByteArray(StandardCharsets.UTF_8)
    }

    private fun Any.toJsonElement(): JsonElement {
        return when (this) {
            is String -> JsonPrimitive(this)
            is Int -> JsonPrimitive(this)
            is Long -> JsonPrimitive(this)
            is Boolean -> JsonPrimitive(this)
            else -> error("Unsupported canonical JSON type: ${this::class.java.name}")
        }
    }

    private fun compareByteArrays(left: ByteArray, right: ByteArray): Int {
        val length = minOf(left.size, right.size)
        for (index in 0 until length) {
            val comparison = (left[index].toInt() and 0xff) - (right[index].toInt() and 0xff)
            if (comparison != 0) {
                return comparison
            }
        }
        return left.size - right.size
    }

    private fun sha256(data: ByteArray): ByteArray {
        return MessageDigest.getInstance("SHA-256").digest(data)
    }

    private fun base64Encode(data: ByteArray): String {
        return Base64.getEncoder().encodeToString(data)
    }

    private fun base64Decode(value: String): ByteArray {
        return Base64.getDecoder().decode(value)
    }
}
