package dev.snapbridge.receiver

import android.content.ContentValues
import android.content.Context
import android.os.Environment
import android.provider.MediaStore

class GallerySaver(private val context: Context) {
    fun saveImage(fileName: String, mimeType: String, bytes: ByteArray): String {
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, fileName.ifBlank { "snapbridge-${System.currentTimeMillis()}" })
            put(MediaStore.Images.Media.MIME_TYPE, mimeType)
            put(
                MediaStore.Images.Media.RELATIVE_PATH,
                Environment.DIRECTORY_PICTURES + "/SnapBridge",
            )
            put(MediaStore.Images.Media.IS_PENDING, 1)
        }
        val resolver = context.contentResolver
        val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
            ?: error("Failed to create MediaStore entry.")
        resolver.openOutputStream(uri)?.use { stream ->
            stream.write(bytes)
        } ?: error("Failed to open MediaStore output stream.")
        resolver.update(
            uri,
            ContentValues().apply {
                put(MediaStore.Images.Media.IS_PENDING, 0)
            },
            null,
            null,
        )
        return uri.toString()
    }
}
