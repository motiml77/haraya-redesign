package com.hourstracker.app.ui

import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.hourstracker.app.data.AppState
import com.hourstracker.app.data.Store
import com.hourstracker.app.data.key
import com.hourstracker.app.export.ReportExporter
import com.hourstracker.app.report.DaySummary
import com.hourstracker.app.report.HEBREW_MONTHS
import com.hourstracker.app.report.WorkSession
import com.hourstracker.app.report.daySummaries
import com.hourstracker.app.report.formatClock
import com.hourstracker.app.report.formatMinutes
import com.hourstracker.app.report.hebrewDayLetter
import com.hourstracker.app.report.hebrewName
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate
import java.time.LocalTime
import java.time.YearMonth
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val DAY_FORMAT = DateTimeFormatter.ofPattern("dd/MM")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(state: AppState, onOpenSettings: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var month by rememberSaveable { mutableStateOf(YearMonth.now()) }
    var confirmToggle by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<WorkSession?>(null) }
    var confirmExport by remember { mutableStateOf(false) }
    var exported by remember { mutableStateOf<Uri?>(null) }

    val now by produceState(System.currentTimeMillis()) {
        while (true) {
            delay(1000)
            value = System.currentTimeMillis()
        }
    }
    val days = daySummaries(state.sessions, month)
    val monthMinutes = days.sumOf { it.totalMinutes(now) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("דיווח שעות", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = onOpenSettings) { Icon(Icons.Filled.Settings, contentDescription = "פרטי העובד") }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Navy,
                    titleContentColor = Color.White,
                    actionIconContentColor = Color.White,
                ),
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { editing = newSession(month) },
                icon = { Icon(Icons.Filled.Add, contentDescription = null) },
                text = { Text("הוספה ידנית") },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { TimerCard(state.running, now, onToggle = { confirmToggle = true }) }

            val previous = YearMonth.now().minusMonths(1)
            val previousPending = previous.key() !in state.exported &&
                daySummaries(state.sessions, previous).isNotEmpty()
            if (previousPending && month != previous) {
                item {
                    Banner(
                        "חודש ${previous.hebrewName()} הסתיים. כדאי לעבור על השעות וליצור את טופס ה-Word.",
                        action = "לחודש ${HEBREW_MONTHS[previous.monthValue - 1]}",
                    ) { month = previous }
                }
            }

            item {
                MonthHeader(
                    month = month,
                    totalMinutes = monthMinutes,
                    workDays = days.size,
                    onPrev = { month = month.minusMonths(1) },
                    onNext = { month = month.plusMonths(1) },
                )
            }

            if (days.isEmpty()) {
                item {
                    Text(
                        "אין עדיין שעות בחודש הזה.",
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(24.dp),
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            items(days, key = { it.date.toString() }) { day ->
                DayCard(day, now, onEdit = { editing = it })
            }

            item { TravelField(month, state.travel[month.key()].orEmpty()) }

            item {
                val done = month.key() in state.exported
                Button(
                    onClick = { confirmExport = true },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    shape = RoundedCornerShape(16.dp),
                ) {
                    Icon(Icons.Filled.Description, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (done) "יצירת הטופס מחדש" else "יצירת טופס Word לחודש", fontSize = 16.sp)
                }
                if (done) {
                    Text(
                        "כבר נוצר טופס לחודש הזה. יצירה מחדש תחליף את הקובץ.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }
            }
        }
    }

    if (confirmToggle) {
        ToggleConfirmDialog(
            running = state.running,
            onConfirm = { note ->
                if (state.running == null) Store.startNow() else Store.stopNow(note)
                confirmToggle = false
            },
            onDismiss = { confirmToggle = false },
        )
    }

    editing?.let { s ->
        SessionEditDialog(
            session = s,
            onSave = { Store.upsert(it); editing = null },
            onDelete = if (s.id == 0L) null else ({ Store.delete(s.id); editing = null }),
            onDismiss = { editing = null },
        )
    }

    if (confirmExport) {
        val running = days.any { d -> d.sessions.any { it.isRunning } }
        val profileMissing = state.profile.name.isBlank()
        AlertDialog(
            onDismissRequest = { confirmExport = false },
            title = { Text("ליצור טופס ל${month.hebrewName()}?") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("סה״כ ${formatMinutes(days.sumOf { d -> d.sessions.filter { !it.isRunning }.sumOf { it.minutes() } })} שעות ב-${days.size} ימים.")
                    if (running) Text("משמרת שעדיין פעילה לא תיכלל בטופס.", color = MaterialTheme.colorScheme.error)
                    if (profileMissing) Text("פרטי העובד עוד לא מולאו (כפתור ההגדרות למעלה).", color = MaterialTheme.colorScheme.error)
                    Text("הקובץ יישמר בתיקייה Documents/${ReportExporter.FOLDER}.", style = MaterialTheme.typography.bodySmall)
                }
            },
            confirmButton = {
                Button(onClick = {
                    confirmExport = false
                    val target = month
                    scope.launch {
                        try {
                            val uri = withContext(Dispatchers.IO) { ReportExporter.export(context, state, target) }
                            Store.markExported(target)
                            exported = uri
                        } catch (e: Exception) {
                            Toast.makeText(context, "שגיאה ביצירת הקובץ: ${e.message}", Toast.LENGTH_LONG).show()
                        }
                    }
                }) { Text("יצירה") }
            },
            dismissButton = { TextButton(onClick = { confirmExport = false }) { Text("ביטול") } },
        )
    }

    exported?.let { uri ->
        val shownMonth = month
        AlertDialog(
            onDismissRequest = { exported = null },
            title = { Text("הטופס נוצר ✓") },
            text = { Text("${ReportExporter.fileName(shownMonth)}\nנשמר בתיקייה Documents/${ReportExporter.FOLDER}") },
            confirmButton = {
                Button(onClick = { ReportExporter.open(context, uri); exported = null }) { Text("פתיחה") }
            },
            dismissButton = {
                Row {
                    TextButton(onClick = { ReportExporter.share(context, uri, shownMonth); exported = null }) { Text("שיתוף") }
                    TextButton(onClick = { exported = null }) { Text("סגירה") }
                }
            },
        )
    }
}

private fun newSession(month: YearMonth): WorkSession {
    val today = LocalDate.now()
    val date = if (YearMonth.from(today) == month) today else month.atDay(1)
    val zone = ZoneId.systemDefault()
    val start = date.atTime(LocalTime.of(8, 0)).atZone(zone).toInstant().toEpochMilli()
    val end = date.atTime(LocalTime.of(12, 0)).atZone(zone).toInstant().toEpochMilli()
    return WorkSession(id = 0, start = start, end = end)
}

private fun formatElapsed(ms: Long): String {
    val s = (ms / 1000).coerceAtLeast(0)
    return "%d:%02d:%02d".format(s / 3600, (s % 3600) / 60, s % 60)
}

@Composable
private fun TimerCard(running: WorkSession?, now: Long, onToggle: () -> Unit) {
    val colors = if (running != null) listOf(GreenDark, Color(0xFF1F7A4D)) else listOf(Navy, NavyLight)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Brush.linearGradient(colors), RoundedCornerShape(24.dp))
            .padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            if (running != null) "במשמרת מאז ${formatClock(running.start)}" else "לא במשמרת",
            color = Color.White.copy(alpha = 0.85f),
            fontSize = 15.sp,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            if (running != null) formatElapsed(now - running.start) else "0:00:00",
            color = Color.White,
            fontSize = 44.sp,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(14.dp))
        Button(
            onClick = onToggle,
            colors = ButtonDefaults.buttonColors(containerColor = if (running != null) Red else Green),
            shape = RoundedCornerShape(32.dp),
            modifier = Modifier
                .fillMaxWidth(0.7f)
                .height(56.dp),
        ) {
            Icon(if (running != null) Icons.Filled.Stop else Icons.Filled.PlayArrow, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(if (running != null) "סיום משמרת" else "התחלת משמרת", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun Banner(text: String, action: String, onClick: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)) {
        Column(Modifier.padding(16.dp)) {
            Text(text, color = MaterialTheme.colorScheme.onTertiaryContainer)
            TextButton(onClick = onClick) { Text(action) }
        }
    }
}

@Composable
private fun MonthHeader(month: YearMonth, totalMinutes: Long, workDays: Int, onPrev: () -> Unit, onNext: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // In RTL the "previous" arrow sits on the right and points right.
            IconButton(onClick = onPrev) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "חודש קודם") }
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                Text(month.hebrewName(), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text(
                    "${formatMinutes(totalMinutes)} שעות · $workDays ימי עבודה",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onNext) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "חודש הבא") }
        }
    }
}

@Composable
private fun DayCard(day: DaySummary, now: Long, onEdit: (WorkSession) -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.padding(vertical = 8.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "${day.date.hebrewDayLetter()}  ${day.date.format(DAY_FORMAT)}",
                    modifier = Modifier.weight(1f),
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    formatMinutes(day.totalMinutes(now)),
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                    fontSize = 18.sp,
                )
            }
            HorizontalDivider(Modifier.padding(horizontal = 16.dp, vertical = 4.dp))
            day.sessions.forEach { s -> SessionRow(s, now) { onEdit(s) } }
        }
    }
}

@Composable
private fun SessionRow(s: WorkSession, now: Long, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(8.dp)
                .background(if (s.isRunning) Green else NavyLight, RoundedCornerShape(4.dp)),
        )
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text("${formatClock(s.start)} – ${s.end?.let { formatClock(it) } ?: "פעיל"}")
            if (s.note.isNotBlank()) {
                Text(s.note, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Text(formatMinutes(s.minutes(now)), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun TravelField(month: YearMonth, saved: String) {
    var text by remember(month) { mutableStateOf(saved) }
    OutlinedTextField(
        value = text,
        onValueChange = {
            text = it
            Store.setTravel(month, it)
        },
        label = { Text("סה״כ נסיעות לחודש (יופיע בטופס)") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        modifier = Modifier.fillMaxWidth(),
    )
}
