package com.hourstracker.app.ui

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.hourstracker.app.report.WorkSession
import com.hourstracker.app.report.formatMinutes
import com.hourstracker.app.report.hebrewDayLetter
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val DATE_FORMAT = DateTimeFormatter.ofPattern("dd/MM/yyyy")
private val TIME_FORMAT = DateTimeFormatter.ofPattern("HH:mm")

/**
 * Add or edit one shift. [session] with id 0 means a new shift.
 * An end time earlier than the start time means the shift ended after midnight.
 */
@Composable
fun SessionEditDialog(
    session: WorkSession,
    onSave: (WorkSession) -> Unit,
    onDelete: (() -> Unit)?,
    onDismiss: () -> Unit,
) {
    val zone = ZoneId.systemDefault()
    val context = LocalContext.current
    val startAt = Instant.ofEpochMilli(session.start).atZone(zone)
    var date by remember { mutableStateOf(startAt.toLocalDate()) }
    var start by remember { mutableStateOf(startAt.toLocalTime().withSecond(0).withNano(0)) }
    var end by remember {
        mutableStateOf(session.end?.let { Instant.ofEpochMilli(it).atZone(zone).toLocalTime().withSecond(0).withNano(0) })
    }
    var note by remember { mutableStateOf(session.note) }
    var confirmDelete by remember { mutableStateOf(false) }

    fun startMillis() = date.atTime(start).atZone(zone).toInstant().toEpochMilli()
    fun endMillis(): Long? = end?.let { e ->
        val endDate = if (!e.isAfter(start)) date.plusDays(1) else date
        endDate.atTime(e).atZone(zone).toInstant().toEpochMilli()
    }

    fun pickTime(initial: LocalTime, onPicked: (LocalTime) -> Unit) {
        TimePickerDialog(context, { _, h, m -> onPicked(LocalTime.of(h, m)) }, initial.hour, initial.minute, true).show()
    }

    if (confirmDelete && onDelete != null) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("למחוק את המשמרת?") },
            text = { Text("${date.format(DATE_FORMAT)}  ${start.format(TIME_FORMAT)}") },
            confirmButton = { Button(onClick = onDelete) { Text("מחיקה") } },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("ביטול") } },
        )
        return
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (session.id == 0L) "הוספת משמרת" else "עריכת משמרת") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                LabeledButton("תאריך", "${date.hebrewDayLetter()}  ${date.format(DATE_FORMAT)}") {
                    DatePickerDialog(context, { _, y, m, d -> date = LocalDate.of(y, m + 1, d) },
                        date.year, date.monthValue - 1, date.dayOfMonth).show()
                }
                LabeledButton("שעת התחלה", start.format(TIME_FORMAT)) { pickTime(start) { start = it } }
                if (session.end == null && session.id != 0L && end == null) {
                    LabeledButton("שעת סיום", "המשמרת פעילה — לקבוע סיום") { pickTime(LocalTime.now()) { end = it } }
                } else {
                    val e = end ?: start.plusHours(1)
                    LabeledButton("שעת סיום", e.format(TIME_FORMAT)) { pickTime(e) { end = it } }
                }
                end?.let { e ->
                    val endMs = endMillis()!!
                    val minutes = WorkSession(0, startMillis(), endMs).minutes()
                    val nextDay = !e.isAfter(start)
                    Text(
                        "סה״כ ${formatMinutes(minutes)} שעות" + if (nextDay) " (מסתיימת למחרת)" else "",
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (minutes > 16 * 60) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("הערות") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            Button(onClick = {
                onSave(session.copy(start = startMillis(), end = if (session.end == null && end == null) null else endMillis(), note = note.trim()))
            }) { Text("שמירה") }
        },
        dismissButton = {
            Row {
                if (onDelete != null) {
                    TextButton(onClick = { confirmDelete = true }) {
                        Text("מחיקה", color = MaterialTheme.colorScheme.error)
                    }
                }
                TextButton(onClick = onDismiss) { Text("ביטול") }
            }
        },
    )
}

@Composable
private fun LabeledButton(label: String, value: String, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
        OutlinedButton(onClick = onClick) { Text(value) }
    }
}
