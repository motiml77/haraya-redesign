package com.hourstracker.app.ui

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import com.hourstracker.app.report.WorkSession
import com.hourstracker.app.storage.Store
import kotlinx.coroutines.delay
import java.time.YearMonth

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT))
        super.onCreate(savedInstanceState)
        Store.init(this)
        setContent {
            HoursTheme {
                val state by Store.state.collectAsState()
                var showSettings by rememberSaveable { mutableStateOf(false) }
                var month by rememberSaveable { mutableStateOf(YearMonth.now()) }
                var editing by remember { mutableStateOf<WorkSession?>(null) }
                val now by produceState(System.currentTimeMillis()) {
                    while (true) {
                        delay(1000)
                        value = System.currentTimeMillis()
                    }
                }

                val current = editing
                when {
                    current != null -> {
                        BackHandler { editing = null }
                        SessionEditScreen(
                            session = current,
                            onSave = { Store.upsert(it); editing = null },
                            onDelete = if (current.id == 0L) null else ({ Store.delete(current.id); editing = null }),
                            onBack = { editing = null },
                        )
                    }
                    showSettings -> {
                        BackHandler { showSettings = false }
                        SettingsScreen(
                            profile = state.profile,
                            onSave = { Store.setProfile(it); showSettings = false },
                            onBack = { showSettings = false },
                        )
                    }
                    else -> HomeScreen(
                        state = state,
                        now = now,
                        month = month,
                        onMonthChange = { month = it },
                        onOpenSettings = { showSettings = true },
                        onEdit = { editing = it },
                    )
                }
            }
        }
    }
}
