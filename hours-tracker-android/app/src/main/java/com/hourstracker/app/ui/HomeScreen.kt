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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Badge
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.hourstracker.app.export.ReportExporter
import com.hourstracker.app.report.DaySummary
import com.hourstracker.app.report.HEBREW_MONTHS
import com.hourstracker.app.report.Profile
import com.hourstracker.app.report.WorkSession
import com.hourstracker.app.report.daySummaries
import com.hourstracker.app.report.formatClock
import com.hourstracker.app.report.formatMinutes
import com.hourstracker.app.report.hebrewName
import com.hourstracker.app.storage.AppState
import com.hourstracker.app.storage.Store
import com.hourstracker.app.storage.key
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.YearMonth
import java.time.ZoneId

private val SHORT_DAYS = listOf("ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳", "א׳")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    state: AppState,
    now: Long,
    month: YearMonth,
    onMonthChange: (YearMonth) -> Unit,
    onOpenSettings: () -> Unit,
    onEdit: (WorkSession) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var confirmToggle by remember { mutableStateOf(false) }
    var confirmExport by remember { mutableStateOf(false) }
    var exported by remember { mutableStateOf<Uri?>(null) }

    val today = Instant.ofEpochMilli(now).atZone(ZoneId.systemDefault()).toLocalDate()
    val days = daySummaries(state.sessions, month)
    val byDate = days.associateBy { it.date }
    val monthMinutes = days.sumOf { it.totalMinutes(now) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("דיווח שעות", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = onOpenSettings) { Icon(Icons.Filled.Badge, contentDescription = "פרטים בטופס") }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Navy,
                    titleContentColor = Color.White,
                    actionIconContentColor = Color.White,
                ),
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { TimerCard(state.running, now, onToggle = { confirmToggle = true }) }

            if (state.profile.name.isBlank()) {
                item {
                    Banner(
                        "עוד לא מילאתם את הפרטים שיופיעו בטופס (שם, ת״ז, בית ספר...).",
                        action = "מילוי פרטים",
                        onClick = onOpenSettings,
                    )
                }
            }

            val previous = YearMonth.from(today).minusMonths(1)
            if (month != previous && previous.key() !in state.exported && daySummaries(state.sessions, previous).isNotEmpty()) {
                item {
                    Banner(
                        "חודש ${previous.hebrewName()} הסתיים. כדאי לעבור על השעות וליצור את טופס ה-Word.",
                        action = "מעבר ל${HEBREW_MONTHS[previous.monthValue - 1]}",
                    ) { onMonthChange(previous) }
                }
            }

            item {
                MonthHeader(
                    month = month,
                    totalMinutes = monthMinutes,
                    workDays = days.size,
                    onPrev = { onMonthChange(month.minusMonths(1)) },
                    onNext = { onMonthChange(month.plusMonths(1)) },
                )
            }

            item {
                Card(
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(20.dp),
                ) {
                    Column(Modifier.padding(vertical = 4.dp)) {
                        Text(
                            "לחיצה על יום מוסיפה שעות · לחיצה על שעות פותחת עריכה",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        )
                        for (d in 1..month.lengthOfMonth()) {
                            val date = month.atDay(d)
                            HorizontalDivider(color = Color(0xFFEEF1F5))
                            DayRow(
                                date = date,
                                summary = byDate[date],
                                isToday = date == today,
                                now = now,
                                onAdd = { onEdit(newSession(date)) },
                                onEdit = onEdit,
                            )
                        }
                    }
                }
            }

            item { TravelField(month, state.travel[month.key()].orEmpty()) }

            item {
                ExportCard(
                    month = month,
                    profile = state.profile,
                    alreadyExported = month.key() in state.exported,
                    onEditDetails = onOpenSettings,
                    onExport = { confirmExport = true },
                )
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

    if (confirmExport) {
        val running = days.any { d -> d.sessions.any { it.isRunning } }
        val finishedMinutes = days.sumOf { d -> d.sessions.filter { !it.isRunning }.sumOf { it.minutes() } }
        AlertDialog(
            onDismissRequest = { confirmExport = false },
            title = { Text("ליצור טופס ל${month.hebrewName()}?") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("סה״כ ${formatMinutes(finishedMinutes)} שעות ב-${days.size} ימים.")
                    if (running) Text("משמרת שעדיין פעילה לא תיכלל בטופס.", color = MaterialTheme.colorScheme.error)
                    Text("הקובץ יישמר בתיקיית ההורדות (Download).", style = MaterialTheme.typography.bodySmall)
                }
            },
            confirmButton = {
                Button(onClick = {
                    confirmExport = false
                    val target = month
                    val snapshot = state
                    scope.launch {
                        try {
                            val uri = withContext(Dispatchers.IO) { ReportExporter.export(context, snapshot, target) }
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
        AlertDialog(
            onDismissRequest = { exported = null },
            title = { Text("הטופס נוצר ✓") },
            text = { Text("${ReportExporter.fileName(month)}\nנשמר בתיקיית ההורדות (Download).") },
            confirmButton = {
                Button(onClick = { ReportExporter.open(context, uri); exported = null }) { Text("פתיחה") }
            },
            dismissButton = {
                Row {
                    TextButton(onClick = { ReportExporter.share(context, uri, month); exported = null }) { Text("שיתוף") }
                    TextButton(onClick = { exported = null }) { Text("סגירה") }
                }
            },
        )
    }
}

/** A new 08:00–12:00 shift on [date], ready to be adjusted in the editor. */
fun newSession(date: LocalDate): WorkSession {
    val zone = ZoneId.systemDefault()
    val start = date.atTime(LocalTime.of(8, 0)).atZone(zone).toInstant().toEpochMilli()
    val end = date.atTime(LocalTime.of(12, 0)).atZone(zone).toInstant().toEpochMilli()
    return WorkSession(id = 0, start = start, end = end)
}

/** Keeps times and file names in left-to-right order inside Hebrew text ("08:00 – 13:30"). */
fun ltr(s: String) = "\u2066$s\u2069"

private fun formatElapsed(ms: Long): String {
    val s = (ms / 1000).coerceAtLeast(0)
    return "%d:%02d:%02d".format(s / 3600, (s % 3600) / 60, s % 60)
}

@Composable
private fun TimerCard(running: WorkSession?, now: Long, onToggle: () -> Unit) {
    val colors = if (running != null) listOf(Color(0xFF0B4A2E), Color(0xFF23915A)) else listOf(Color(0xFF1B3354), Color(0xFF3A6EA5))
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Brush.linearGradient(colors), RoundedCornerShape(28.dp))
            .padding(horizontal = 20.dp, vertical = 22.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            if (running != null) "● במשמרת מאז ${formatClock(running.start)}" else "לא במשמרת",
            color = Color.White,
            fontSize = 14.sp,
            modifier = Modifier
                .background(Color.White.copy(alpha = 0.2f), RoundedCornerShape(12.dp))
                .padding(horizontal = 12.dp, vertical = 4.dp),
        )
        Spacer(Modifier.height(10.dp))
        Text(
            if (running != null) formatElapsed(now - running.start) else "0:00:00",
            color = Color.White,
            fontSize = 48.sp,
            fontWeight = FontWeight.Medium,
        )
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = onToggle,
            colors = ButtonDefaults.buttonColors(containerColor = if (running != null) Red else Green),
            shape = RoundedCornerShape(32.dp),
            modifier = Modifier
                .fillMaxWidth(0.75f)
                .height(60.dp),
        ) {
            Icon(if (running != null) Icons.Filled.Stop else Icons.Filled.PlayArrow, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(if (running != null) "סיום משמרת" else "התחלת משמרת", fontSize = 19.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun Banner(text: String, action: String, onClick: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)) {
        Column(Modifier.padding(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 4.dp)) {
            Text(text, color = MaterialTheme.colorScheme.onTertiaryContainer)
            TextButton(onClick = onClick) { Text(action, fontWeight = FontWeight.Bold) }
        }
    }
}

@Composable
private fun MonthHeader(month: YearMonth, totalMinutes: Long, workDays: Int, onPrev: () -> Unit, onNext: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // RTL: "previous" sits on the right and points right.
        IconButton(onClick = onPrev) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "חודש קודם") }
        Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(month.hebrewName(), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp)) {
                StatChip("${formatMinutes(totalMinutes)} שעות")
                StatChip("$workDays ימי עבודה")
            }
        }
        IconButton(onClick = onNext) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "חודש הבא") }
    }
}

@Composable
private fun StatChip(text: String) {
    Text(
        text,
        color = Navy,
        fontWeight = FontWeight.Bold,
        modifier = Modifier
            .background(MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(10.dp))
            .padding(horizontal = 12.dp, vertical = 4.dp),
    )
}

@Composable
private fun DayRow(
    date: LocalDate,
    summary: DaySummary?,
    isToday: Boolean,
    now: Long,
    onAdd: () -> Unit,
    onEdit: (WorkSession) -> Unit,
) {
    val weekend = date.dayOfWeek == DayOfWeek.FRIDAY || date.dayOfWeek == DayOfWeek.SATURDAY
    val single = summary?.sessions?.singleOrNull()
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { if (single != null) onEdit(single) else if (summary == null) onAdd() }
            .heightIn(min = 54.dp)
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(42.dp)
                .background(
                    when {
                        isToday -> Navy
                        summary != null -> MaterialTheme.colorScheme.primaryContainer
                        weekend -> Color(0xFFF1F2F4)
                        else -> Color.Transparent
                    },
                    CircleShape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    date.dayOfMonth.toString(),
                    fontWeight = FontWeight.Bold,
                    fontSize = 15.sp,
                    lineHeight = 16.sp,
                    color = if (isToday) Color.White else Navy,
                )
                Text(
                    SHORT_DAYS[date.dayOfWeek.value - 1],
                    fontSize = 10.sp,
                    lineHeight = 11.sp,
                    color = if (isToday) Color.White.copy(alpha = 0.85f) else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.width(12.dp))
        if (summary == null) {
            Text("—", color = Color(0xFFB8BEC8), modifier = Modifier.weight(1f))
            Icon(Icons.Filled.Add, contentDescription = "הוספת שעות", tint = Color(0xFF9DB3CC))
        } else {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                summary.sessions.forEach { s ->
                    Row(
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .clickable { onEdit(s) }
                            .padding(vertical = 2.dp, horizontal = 2.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            ltr("${formatClock(s.start)} – ${s.end?.let { formatClock(it) } ?: "עכשיו"}"),
                            fontSize = 16.sp,
                            color = if (s.isRunning) GreenDark else Color(0xFF1C2430),
                            fontWeight = if (s.isRunning) FontWeight.Bold else FontWeight.Normal,
                        )
                        Spacer(Modifier.width(6.dp))
                        Icon(Icons.Filled.Edit, contentDescription = "עריכה", modifier = Modifier.size(14.dp), tint = Color(0xFF9DB3CC))
                    }
                    if (s.note.isNotBlank()) {
                        Text(s.note, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            Text(
                formatMinutes(summary.totalMinutes(now)),
                fontWeight = FontWeight.Bold,
                fontSize = 17.sp,
                color = Navy,
                textAlign = TextAlign.Center,
                modifier = Modifier.width(52.dp),
            )
            IconButton(onClick = onAdd, modifier = Modifier.size(32.dp)) {
                Icon(Icons.Filled.Add, contentDescription = "משמרת נוספת", tint = Color(0xFF9DB3CC), modifier = Modifier.size(18.dp))
            }
        }
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

@Composable
private fun ExportCard(
    month: YearMonth,
    profile: Profile,
    alreadyExported: Boolean,
    onEditDetails: () -> Unit,
    onExport: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(20.dp),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("טופס Word ל${month.hebrewName()}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.background, RoundedCornerShape(12.dp))
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                DetailLine("שם העובד", profile.name)
                DetailLine("ת״ז", profile.idNumber)
                DetailLine("כתובת מגורים", profile.address)
                DetailLine("תפקיד", profile.role)
                DetailLine("מקום עבודה", profile.workplace)
            }
            OutlinedButton(onClick = onEditDetails, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Filled.Edit, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("עריכת הפרטים בטופס")
            }
            Button(
                onClick = onExport,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                shape = RoundedCornerShape(16.dp),
            ) {
                Icon(Icons.Filled.Description, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(if (alreadyExported) "יצירת הטופס מחדש" else "יצירת טופס Word", fontSize = 17.sp)
            }
            Text(
                if (alreadyExported) "כבר נוצר טופס לחודש הזה. יצירה מחדש תחליף את הקובץ בתיקיית ההורדות."
                else "הקובץ יישמר בתיקיית ההורדות (Download):\n${ltr(ReportExporter.fileName(month))}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun DetailLine(label: String, value: String) {
    Row {
        Text("$label: ", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 14.sp)
        Text(
            value.ifBlank { "לא מולא" },
            fontSize = 14.sp,
            fontWeight = if (value.isBlank()) FontWeight.Normal else FontWeight.Bold,
            color = if (value.isBlank()) MaterialTheme.colorScheme.error else Color(0xFF1C2430),
        )
    }
}
