package com.hourstracker.app.ui

import android.content.Context
import android.widget.FrameLayout
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.painterResource
import com.hourstracker.app.R
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.github.takahirom.roborazzi.ExperimentalRoborazziApi
import com.github.takahirom.roborazzi.captureRoboImage
import com.github.takahirom.roborazzi.captureScreenRoboImage
import com.hourstracker.app.report.Profile
import com.hourstracker.app.report.WorkSession
import com.hourstracker.app.storage.AppState
import com.hourstracker.app.widget.TimerWidget
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.time.LocalDateTime
import java.time.YearMonth
import java.time.ZoneId

/** Renders the main screens and the widget with sample data into app/screenshots/. */
@OptIn(ExperimentalRoborazziApi::class)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w400dp-h860dp-xxhdpi")
class ScreenshotTest {
    @get:Rule
    val compose = createComposeRule()

    private val zone = ZoneId.systemDefault()
    private fun at(d: Int, h: Int, m: Int) = LocalDateTime.of(2026, 10, d, h, m).atZone(zone).toInstant().toEpochMilli()

    private val now = at(26, 10, 42)
    private val profile = Profile("ישראל ישראלי", "123456789", "הרימון 5, קרני שומרון", "מדריך", "בית ספר אלומות")
    private val finished = listOf(
        WorkSession(1, at(1, 8, 0), at(1, 13, 30)),
        WorkSession(2, at(4, 8, 15), at(4, 14, 0)),
        WorkSession(3, at(5, 8, 0), at(5, 12, 30), "ישיבת צוות"),
        WorkSession(4, at(5, 14, 0), at(5, 16, 15)),
        WorkSession(5, at(6, 7, 45), at(6, 13, 0)),
        WorkSession(6, at(11, 8, 0), at(11, 14, 30)),
        WorkSession(7, at(12, 9, 0), at(12, 15, 0)),
        WorkSession(8, at(13, 8, 0), at(13, 13, 45)),
        WorkSession(9, at(18, 8, 0), at(18, 14, 0)),
        WorkSession(10, at(19, 8, 30), at(19, 12, 0), "טיול שנתי"),
        WorkSession(11, at(20, 8, 0), at(20, 13, 0)),
        WorkSession(12, at(25, 8, 0), at(25, 14, 15)),
    )
    private val running = WorkSession(13, at(26, 8, 0), null)
    private val idleState = AppState(sessions = finished, travel = mapOf("2026-10" to "120"), profile = profile)
    private val runningState = idleState.copy(sessions = finished + running)

    @Test
    fun home() {
        compose.setContent {
            HoursTheme { HomeScreen(runningState, now, YearMonth.of(2026, 10), {}, {}, {}) }
        }
        compose.onRoot().captureRoboImage("screenshots/1_home.png")
    }

    @Test
    @Config(qualifiers = "w400dp-h2900dp-xxhdpi")
    fun homeFullMonth() {
        compose.setContent {
            HoursTheme { HomeScreen(idleState, now, YearMonth.of(2026, 10), {}, {}, {}) }
        }
        compose.onRoot().captureRoboImage("screenshots/2_home_full_month.png")
    }

    @Test
    fun editShift() {
        compose.setContent {
            HoursTheme { SessionEditScreen(finished[2], {}, {}, {}) }
        }
        compose.onRoot().captureRoboImage("screenshots/3_edit_shift.png")
    }

    @Test
    fun formDetails() {
        compose.setContent {
            HoursTheme { SettingsScreen(profile, {}, {}) }
        }
        compose.onRoot().captureRoboImage("screenshots/4_form_details.png")
    }

    @Test
    fun confirmStart() {
        compose.setContent {
            HoursTheme { Box(Modifier.fillMaxSize().background(Color(0xFFF4F6FA))) { ToggleConfirmDialog(null, { _, _ -> }, {}) } }
        }
        captureScreenRoboImage("screenshots/6_confirm_start.png")
    }

    @Test
    fun logo() {
        compose.setContent {
            Box(Modifier.fillMaxSize().background(Color.White), contentAlignment = Alignment.Center) {
                Image(
                    painter = painterResource(R.drawable.ic_logo),
                    contentDescription = null,
                    modifier = Modifier.size(300.dp).clip(RoundedCornerShape(64.dp)),
                )
            }
        }
        compose.onRoot().captureRoboImage("screenshots/8_logo.png")
    }

    @Test
    fun widgets() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        compose.setContent {
            Box(
                Modifier
                    .fillMaxSize()
                    .background(Brush.verticalGradient(listOf(Color(0xFF8EC5FC), Color(0xFFE0C3FC)))),
            ) {
                androidx.compose.foundation.layout.Column(Modifier.padding(16.dp)) {
                    listOf(idleState, runningState).forEach { state ->
                        AndroidView(
                            factory = { ctx -> TimerWidget.buildViews(context, state, now).apply(ctx, FrameLayout(ctx)) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(bottom = 16.dp)
                                .height(62.dp),
                        )
                    }
                }
            }
        }
        compose.onRoot().captureRoboImage("screenshots/5_widgets.png")
    }
}
