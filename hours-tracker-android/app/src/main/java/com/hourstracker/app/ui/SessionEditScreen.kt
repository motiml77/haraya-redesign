package com.hourstracker.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TimePicker
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.hourstracker.app.report.HEBREW_MONTHS
import com.hourstracker.app.report.WorkSession
import com.hourstracker.app.report.formatMinutes
import com.hourstracker.app.report.hebrewDayLetter
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

private val TIME_FORMAT = DateTimeFormatter.ofPattern("HH:mm")

private fun LocalDate.hebrewLong() = "${hebrewDayLetter()}, $dayOfMonth ב${HEBREW_MONTHS[monthValue - 1]} $year"

/**
 * Full-screen editor for one shift. [session] with id 0 is a new shift.
 * An end time earlier than the start time means the shift ended after midnight.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionEditScreen(
    session: WorkSession,
    onSave: (WorkSession) -> Unit,
    onDelete: (() -> Unit)?,
    onBack: () -> Unit,
) {
    val zone = ZoneId.systemDefault()
    val startAt = Instant.ofEpochMilli(session.start).atZone(zone)
    var date by remember { mutableStateOf(startAt.toLocalDate()) }
    var start by remember { mutableStateOf(startAt.toLocalTime().withSecond(0).withNano(0)) }
    var end by remember {
        mutableStateOf(session.end?.let { Instant.ofEpochMilli(it).atZone(zone).toLocalTime().withSecond(0).withNano(0) })
    }
    var note by remember { mutableStateOf(session.note) }
    var pickDate by remember { mutableStateOf(false) }
    var pickStart by remember { mutableStateOf(false) }
    var pickEnd by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }

    val startMillis = date.atTime(start).atZone(zone).toInstant().toEpochMilli()
    val endMillis = end?.let { e ->
        val endDate = if (!e.isAfter(start)) date.plusDays(1) else date
        endDate.atTime(e).atZone(zone).toInstant().toEpochMilli()
    }
    val minutes = endMillis?.let { WorkSession(0, startMillis, it).minutes() }
    val invalid = end != null && end == start

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (session.id == 0L) "הוספת שעות" else "עריכת שעות", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "חזרה") }
                },
                actions = {
                    if (onDelete != null) {
                        IconButton(onClick = { confirmDelete = true }) { Icon(Icons.Filled.Delete, contentDescription = "מחיקה") }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Navy,
                    titleContentColor = Color.White,
                    navigationIconContentColor = Color.White,
                    actionIconContentColor = Color.White,
                ),
            )
        },
        bottomBar = {
            Surface(shadowElevation = 8.dp, color = Color.White) {
                Button(
                    onClick = { onSave(session.copy(start = startMillis, end = endMillis, note = note.trim())) },
                    enabled = !invalid,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding()
                        .padding(16.dp)
                        .height(56.dp),
                ) { Text("שמירה", fontSize = 18.sp, fontWeight = FontWeight.Bold) }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            SectionTitle("תאריך")
            Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(20.dp)) {
                Row(Modifier.padding(6.dp), verticalAlignment = Alignment.CenterVertically) {
                    // RTL: previous day on the right, next day on the left.
                    IconButton(onClick = { date = date.minusDays(1) }) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "יום קודם")
                    }
                    Row(
                        Modifier
                            .weight(1f)
                            .clickable { pickDate = true }
                            .padding(vertical = 12.dp),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Filled.CalendarMonth, contentDescription = null, tint = NavyLight)
                        Spacer(Modifier.width(8.dp))
                        Text(date.hebrewLong(), fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Navy)
                    }
                    IconButton(onClick = { date = date.plusDays(1) }) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "יום הבא")
                    }
                }
            }

            SectionTitle("שעות")
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                TimeBox(
                    label = "התחלה",
                    time = start.format(TIME_FORMAT),
                    modifier = Modifier.weight(1f),
                    onClick = { pickStart = true },
                    onMinus = { start = start.minusMinutes(15) },
                    onPlus = { start = start.plusMinutes(15) },
                )
                TimeBox(
                    label = "סיום",
                    time = end?.format(TIME_FORMAT) ?: "עדיין פעילה",
                    modifier = Modifier.weight(1f),
                    onClick = { pickEnd = true },
                    onMinus = { end = (end ?: LocalTime.now().withSecond(0).withNano(0)).minusMinutes(15) },
                    onPlus = { end = (end ?: LocalTime.now().withSecond(0).withNano(0)).plusMinutes(15) },
                )
            }

            Card(
                colors = CardDefaults.cardColors(
                    containerColor = if (invalid) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
                ),
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    when {
                        invalid -> Text("שעת הסיום זהה לשעת ההתחלה", color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.Bold)
                        minutes == null || end == null -> Text("המשמרת עדיין פעילה — אפשר לקבוע שעת סיום למעלה", color = GreenDark)
                        else -> {
                            val total: Long = minutes ?: 0L
                            Text("סה״כ", color = GreenDark)
                            Text("${formatMinutes(total)} שעות", fontSize = 28.sp, fontWeight = FontWeight.Bold, color = GreenDark)
                            if (end?.isAfter(start) == false) Text("המשמרת מסתיימת למחרת", color = GreenDark)
                            if (total > 16 * 60) Text("משמרת ארוכה מ-16 שעות — כדאי לבדוק", color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }

            SectionTitle("הערות (יופיעו בטופס)")
            OutlinedTextField(
                value = note,
                onValueChange = { note = it },
                placeholder = { Text("לא חובה") },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }

    if (pickDate) {
        val state = rememberDatePickerState(initialSelectedDateMillis = date.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli())
        DatePickerDialog(
            onDismissRequest = { pickDate = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let { date = Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate() }
                    pickDate = false
                }) { Text("אישור") }
            },
            dismissButton = { TextButton(onClick = { pickDate = false }) { Text("ביטול") } },
        ) { DatePicker(state = state) }
    }
    if (pickStart) {
        TimePickDialog(start, onPicked = { start = it; pickStart = false }, onDismiss = { pickStart = false })
    }
    if (pickEnd) {
        TimePickDialog(end ?: LocalTime.now(), onPicked = { end = it; pickEnd = false }, onDismiss = { pickEnd = false })
    }
    if (confirmDelete && onDelete != null) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("למחוק את השעות האלה?") },
            text = { Text("${date.hebrewLong()}, ${start.format(TIME_FORMAT)}") },
            confirmButton = {
                Button(onClick = onDelete, colors = ButtonDefaults.buttonColors(containerColor = Red)) { Text("מחיקה") }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("ביטול") } },
        )
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun TimeBox(
    label: String,
    time: String,
    modifier: Modifier,
    onClick: () -> Unit,
    onMinus: () -> Unit,
    onPlus: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(20.dp),
        modifier = modifier,
    ) {
        Column(Modifier.padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(
                time,
                fontSize = if (time.length > 5) 20.sp else 36.sp,
                fontWeight = FontWeight.Bold,
                color = Navy,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(14.dp))
                    .clickable(onClick = onClick)
                    .padding(vertical = 10.dp),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            )
            Spacer(Modifier.height(8.dp))
            // Keep "−15 / +15" in reading order regardless of RTL.
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    SmallStep("−15", onMinus, Modifier.weight(1f))
                    SmallStep("+15", onPlus, Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
private fun SmallStep(text: String, onClick: () -> Unit, modifier: Modifier) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.height(40.dp),
        shape = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, Color(0xFFD0D9E4)),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp),
    ) { Text(text, fontWeight = FontWeight.Bold) }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TimePickDialog(initial: LocalTime, onPicked: (LocalTime) -> Unit, onDismiss: () -> Unit) {
    val state = rememberTimePickerState(initialHour = initial.hour, initialMinute = initial.minute, is24Hour = true)
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = { onPicked(LocalTime.of(state.hour, state.minute)) }) { Text("אישור") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("ביטול") } },
        text = {
            // The clock face reads left-to-right (hours:minutes).
            CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) { TimePicker(state = state) }
        },
    )
}
