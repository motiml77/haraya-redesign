package com.hourstracker.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.hourstracker.app.report.WorkSession
import com.hourstracker.app.report.formatClock
import com.hourstracker.app.report.formatMinutes

/**
 * Confirmation before starting or stopping the timer, so a stray tap never changes anything.
 * When stopping, an optional note can be added to the shift.
 */
@Composable
fun ToggleConfirmDialog(
    running: WorkSession?,
    onConfirm: (note: String) -> Unit,
    onDismiss: () -> Unit,
) {
    var note by remember { mutableStateOf("") }
    val now = System.currentTimeMillis()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (running == null) "להתחיל משמרת?" else "לסיים את המשמרת?") },
        text = {
            Column {
                if (running == null) {
                    Text("שעת התחלה: ${formatClock(now)}")
                } else {
                    Text("התחלת ב-${formatClock(running.start)}, עד עכשיו ${formatMinutes(running.minutes(now))} שעות.")
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = note,
                        onValueChange = { note = it },
                        label = { Text("הערה (לא חובה)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onConfirm(note) },
                colors = ButtonDefaults.buttonColors(containerColor = if (running == null) Green else Red),
            ) { Text(if (running == null) "כן, להתחיל" else "כן, לסיים") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("ביטול") } },
    )
}
