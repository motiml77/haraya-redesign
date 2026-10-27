package com.hourstracker.app.ui

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.hourstracker.app.storage.Store
import com.hourstracker.app.report.formatClock
import com.hourstracker.app.report.formatMinutes

/** Transparent activity opened by the widget button; shows only the confirmation dialog. */
class ConfirmActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Store.init(this)
        val running = Store.state.value.running
        setContent {
            HoursTheme {
                ToggleConfirmDialog(
                    running = running,
                    onConfirm = { note, at ->
                        if (running == null) {
                            Store.startNow(at)?.let { toast("המשמרת התחילה ב-${formatClock(it.start)}") }
                        } else {
                            Store.stopNow(note, at)?.let { toast("המשמרת נשמרה: ${formatMinutes(it.minutes())} שעות") }
                        }
                        finish()
                    },
                    onDismiss = { finish() },
                )
            }
        }
    }

    private fun toast(text: String) = Toast.makeText(this, text, Toast.LENGTH_SHORT).show()
}
