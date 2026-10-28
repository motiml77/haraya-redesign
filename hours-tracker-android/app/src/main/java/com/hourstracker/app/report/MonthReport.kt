package com.hourstracker.app.report

import java.time.Instant
import java.time.LocalDate
import java.time.YearMonth
import java.time.ZoneId
import java.time.format.DateTimeFormatter

val HEBREW_MONTHS = listOf(
    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
)

private val HEBREW_DAYS = listOf("ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳", "א׳")

fun YearMonth.hebrewName(): String = "${HEBREW_MONTHS[monthValue - 1]} $year"

fun LocalDate.hebrewDayLetter(): String = "יום " + HEBREW_DAYS[dayOfWeek.value - 1]

/** 452 -> "7:32" */
fun formatMinutes(minutes: Long): String = "%d:%02d".format(minutes / 60, minutes % 60)

private val HOUR_MINUTE = DateTimeFormatter.ofPattern("HH:mm")

fun formatClock(epochMillis: Long, zone: ZoneId = ZoneId.systemDefault()): String =
    Instant.ofEpochMilli(epochMillis).atZone(zone).format(HOUR_MINUTE)

fun WorkSession.date(zone: ZoneId = ZoneId.systemDefault()): LocalDate =
    Instant.ofEpochMilli(start).atZone(zone).toLocalDate()

/** All sessions of one calendar day (by start time), already sorted. */
data class DaySummary(
    val date: LocalDate,
    val sessions: List<WorkSession>,
) {
    val firstStart: Long get() = sessions.first().start

    /** End of the last session, or null while that session is still running. */
    val lastEnd: Long? get() = sessions.last().end

    fun totalMinutes(now: Long = System.currentTimeMillis()): Long = sessions.sumOf { it.minutes(now) }

    /** Text for the "הערות" column: the separate intervals when there were several, plus user notes. */
    fun notesText(zone: ZoneId = ZoneId.systemDefault()): String {
        val parts = mutableListOf<String>()
        if (sessions.size > 1) {
            parts += sessions.joinToString(", ") { s ->
                formatClock(s.start, zone) + "-" + (s.end?.let { formatClock(it, zone) } ?: "")
            }
        }
        sessions.map { it.note.trim().replace('\n', ' ') }.filter { it.isNotEmpty() }.forEach { parts += it }
        return parts.joinToString(" · ")
    }
}

fun daySummaries(
    sessions: List<WorkSession>,
    month: YearMonth,
    zone: ZoneId = ZoneId.systemDefault(),
): List<DaySummary> =
    sessions
        .filter { YearMonth.from(it.date(zone)) == month }
        .sortedBy { it.start }
        .groupBy { it.date(zone) }
        .map { (date, list) -> DaySummary(date, list) }
        .sortedBy { it.date }

/** Values for every {{PLACEHOLDER}} in report_template.docx. */
fun reportValues(
    profile: Profile,
    month: YearMonth,
    days: List<DaySummary>,
    travel: String,
    today: LocalDate,
    zone: ZoneId = ZoneId.systemDefault(),
): Map<String, String> {
    fun orBlank(v: String, width: Int = 14) = v.trim().ifEmpty { "_".repeat(width) }

    val values = mutableMapOf(
        "DATE" to today.format(DateTimeFormatter.ofPattern("dd/MM/yyyy")),
        "MONTH" to month.hebrewName(),
        "NAME" to orBlank(profile.name),
        "ID" to orBlank(profile.idNumber, 12),
        "ADDRESS" to orBlank(profile.address),
        "ROLE" to orBlank(profile.role),
        "WORKPLACE" to orBlank(profile.workplace, 23),
        "MONTH_NAME" to HEBREW_MONTHS[month.monthValue - 1],
        "YEAR" to month.year.toString(),
        "TRAVEL" to orBlank(travel, 12),
    )
    // Running sessions are not reported until they are stopped.
    var total = 0L
    var reportedDays = 0
    for (day in days) {
        val finished = day.sessions.filter { !it.isRunning }
        if (finished.isEmpty()) continue
        val summary = DaySummary(day.date, finished)
        val minutes = summary.totalMinutes()
        total += minutes
        reportedDays++
        val d = day.date.dayOfMonth
        values["S$d"] = formatClock(summary.firstStart, zone)
        values["E$d"] = summary.lastEnd?.let { formatClock(it, zone) } ?: ""
        values["T$d"] = formatMinutes(minutes)
        values["N$d"] = summary.notesText(zone)
    }
    // A month with nothing recorded yet gives a completely blank form (no "0:00").
    values["TOTAL_HOURS"] = if (reportedDays == 0) "" else formatMinutes(total)
    return values
}
