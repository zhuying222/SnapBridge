package dev.snapbridge.receiver

import fi.iki.elonen.NanoHTTPD
import java.io.IOException
import java.net.URLDecoder
import kotlin.text.Charsets.UTF_8
import kotlinx.serialization.SerializationException
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json

class ReceiverHttpServer(
    private val transferServer: TransferServer,
    port: Int,
) : NanoHTTPD("0.0.0.0", port) {
    private val json = Json { ignoreUnknownKeys = true }

    override fun serve(session: IHTTPSession): Response {
        return try {
            when {
                session.method == Method.GET && session.uri == "/api/v1/pairing/challenge" ->
                    transferServer.pairingChallengeResponse().toNanoResponse()

                session.method == Method.POST && session.uri == "/api/v1/pairing/requests" -> {
                    val payload = json.decodeFromString<PairingRequestPayload>(readRequestBody(session))
                    transferServer.pairingRequestResponse(payload).toNanoResponse()
                }

                session.method == Method.GET && session.uri.startsWith("/api/v1/pairing/requests/") -> {
                    val requestId = URLDecoder.decode(
                        session.uri.removePrefix("/api/v1/pairing/requests/"),
                        UTF_8.name(),
                    )
                    transferServer.pairingStatusResponse(requestId).toNanoResponse()
                }

                session.method == Method.POST && session.uri == "/api/v1/captures" -> {
                    val payload = json.decodeFromString<CapturePayload>(readRequestBody(session))
                    transferServer.captureResponse(payload).toNanoResponse()
                }

                else -> simpleResponse(
                    status = Response.Status.NOT_FOUND,
                    body = """{"reason":"not_found"}""",
                )
            }
        } catch (_: SerializationException) {
            transferServer.badJsonResponse().toNanoResponse()
        } catch (_: IOException) {
            simpleResponse(
                status = Response.Status.BAD_REQUEST,
                body = """{"reason":"invalid_request_body"}""",
            )
        } catch (exception: ResponseException) {
            simpleResponse(
                status = exception.status,
                body = """{"reason":"${exception.message ?: "request_error"}"}""",
            )
        } catch (_: Exception) {
            simpleResponse(
                status = Response.Status.INTERNAL_ERROR,
                body = """{"reason":"internal_server_error"}""",
            )
        }
    }

    private fun readRequestBody(session: IHTTPSession): String {
        val files = HashMap<String, String>()
        session.parseBody(files)
        return files["postData"].orEmpty()
    }

    private fun ApiResponse.toNanoResponse(): Response {
        return simpleResponse(mapStatus(statusCode), body)
    }

    private fun simpleResponse(status: Response.IStatus, body: String): Response {
        return newFixedLengthResponse(status, "application/json; charset=utf-8", body)
    }

    private fun mapStatus(statusCode: Int): Response.IStatus {
        return when (statusCode) {
            200 -> Response.Status.OK
            400 -> Response.Status.BAD_REQUEST
            401 -> Response.Status.UNAUTHORIZED
            404 -> Response.Status.NOT_FOUND
            409 -> Response.Status.CONFLICT
            410 -> Response.Status.GONE
            else -> Response.Status.INTERNAL_ERROR
        }
    }
}
