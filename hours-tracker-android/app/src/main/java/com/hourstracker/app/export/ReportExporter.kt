package com.hourstracker.app.export

import android.content.ActivityNotFoundException
import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import android.widget.Toast
import com.hourstracker.app.storage.AppState
import com.hourstracker.app.storage.Store
import com.hourstracker.app.storage.key
import com.hourstracker.app.report.DocxFiller
import com.hourstracker.app.report.daySummaries
import com.hourstracker.app.report.reportValues
import java.time.LocalDate
import java.time.YearMonth

/** Writes the monthly Word report to the phone's Download folder, one file per month (re-exporting replaces it). */
object ReportExporter {
    private const val DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    fun fileName(month: YearMonth) = "דוח שעות ${month.key()}.docx"

    fun export(context: Context, state: AppState, month: YearMonth): Uri {
        val values = reportValues(
            profile = state.profile,
            month = month,
            days = daySummaries(state.sessions, month),
            travel = state.travel[month.key()].orEmpty(),
            today = LocalDate.now(),
        )
        val signaturePng = if (state.signatureAt > 0) Store.signaturePng() else null
        val resolver = context.contentResolver
        val relativePath = Environment.DIRECTORY_DOWNLOADS + "/"
        val name = fileName(month)
        val collection = MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)

        // Only files this app created are visible here, so an older copy is replaced in place.
        val existing = resolver.query(
            collection,
            arrayOf(MediaStore.MediaColumns._ID),
            "${MediaStore.MediaColumns.RELATIVE_PATH}=? AND ${MediaStore.MediaColumns.DISPLAY_NAME}=?",
            arrayOf(relativePath, name),
            null,
        )?.use { c -> if (c.moveToFirst()) ContentUris.withAppendedId(collection, c.getLong(0)) else null }

        val uri = existing ?: resolver.insert(collection, ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, name)
            put(MediaStore.MediaColumns.MIME_TYPE, DOCX_MIME)
            put(MediaStore.MediaColumns.RELATIVE_PATH, relativePath)
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }) ?: error("לא ניתן ליצור קובץ בתיקיית ההורדות")

        resolver.openOutputStream(uri, "wt")!!.use { out ->
            context.assets.open("report_template.docx").use { template ->
                DocxFiller.fill(template, values, out, signaturePng)
            }
        }
        if (existing == null) {
            resolver.update(uri, ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }, null, null)
        }
        return uri
    }

    fun open(context: Context, uri: Uri) {
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, DOCX_MIME)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            context.startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(context, "לא נמצאה אפליקציה לפתיחת קובצי Word", Toast.LENGTH_LONG).show()
        }
    }

    fun share(context: Context, uri: Uri, month: YearMonth) {
        val send = Intent(Intent.ACTION_SEND)
            .setType(DOCX_MIME)
            .putExtra(Intent.EXTRA_STREAM, uri)
            .putExtra(Intent.EXTRA_SUBJECT, fileName(month).removeSuffix(".docx"))
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        context.startActivity(Intent.createChooser(send, "שיתוף הדוח").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
