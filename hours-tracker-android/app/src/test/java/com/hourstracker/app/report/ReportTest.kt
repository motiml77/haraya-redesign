package com.hourstracker.app.report

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.YearMonth
import java.time.ZoneId
import java.util.zip.ZipInputStream

class ReportTest {
    private val zone = ZoneId.of("Asia/Jerusalem")

    private fun at(y: Int, mo: Int, d: Int, h: Int, mi: Int) =
        LocalDateTime.of(y, mo, d, h, mi).atZone(zone).toInstant().toEpochMilli()

    private val sessions = listOf(
        WorkSession(1, at(2026, 10, 5, 8, 0), at(2026, 10, 5, 12, 30), "בוקר"),
        WorkSession(2, at(2026, 10, 5, 14, 0), at(2026, 10, 5, 16, 15)),
        WorkSession(3, at(2026, 10, 12, 9, 5), at(2026, 10, 12, 17, 0)),
        WorkSession(4, at(2026, 10, 31, 22, 0), at(2026, 11, 1, 1, 0), "לילה & <חירום>"),
        WorkSession(5, at(2026, 9, 30, 8, 0), at(2026, 9, 30, 9, 0)),
        WorkSession(6, at(2026, 10, 26, 8, 0), null),
    )

    @Test
    fun roundsToFiveMinutes() {
        fun hm(h: Int, m: Int, s: Int = 0) = LocalDateTime.of(2026, 10, 5, h, m, s).atZone(zone).toInstant().toEpochMilli()
        fun shown(ms: Long) = formatClock(roundToFiveMinutes(ms), zone)
        assertEquals("07:30", shown(hm(7, 32, 29)))
        assertEquals("07:35", shown(hm(7, 32, 30)))
        assertEquals("07:35", shown(hm(7, 35)))
        assertEquals("07:35", shown(hm(7, 37, 29)))
        assertEquals("07:40", shown(hm(7, 38)))
        assertEquals("08:00", shown(hm(7, 57, 30)))
        assertEquals("00:00", shown(hm(23, 58)))
    }

    @Test
    fun formatsMinutes() {
        assertEquals("0:00", formatMinutes(0))
        assertEquals("7:32", formatMinutes(452))
        assertEquals("152:30", formatMinutes(9150))
    }

    @Test
    fun groupsByDayWithinMonth() {
        val days = daySummaries(sessions, YearMonth.of(2026, 10), zone)
        assertEquals(listOf(5, 12, 26, 31), days.map { it.date.dayOfMonth })
        assertEquals(270L + 135L, days[0].totalMinutes())
        assertEquals("08:00-12:30, 14:00-16:15 · בוקר", days[0].notesText(zone))
    }

    @Test
    fun buildsReportValues() {
        val days = daySummaries(sessions, YearMonth.of(2026, 10), zone)
        val v = reportValues(Profile(name = "ישראל ישראלי"), YearMonth.of(2026, 10), days, "", LocalDate.of(2026, 11, 1), zone)
        assertEquals("08:00", v["S5"])
        assertEquals("16:15", v["E5"])
        assertEquals("6:45", v["T5"])
        assertEquals("7:55", v["T12"])
        assertEquals("3:00", v["T31"])
        assertEquals("01:00", v["E31"])
        assertFalse("running session is not reported", v.containsKey("S26"))
        assertEquals("17:40", v["TOTAL_HOURS"])
        assertEquals("אוקטובר 2026", v["MONTH"])
        assertEquals("01/11/2026", v["DATE"])
        assertEquals("ישראל ישראלי", v["NAME"])
        assertTrue(v["ID"]!!.all { it == '_' })
    }

    @Test
    fun fillsTemplate() {
        val template = File("src/main/assets/report_template.docx").readBytes()
        val days = daySummaries(sessions, YearMonth.of(2026, 10), zone)
        val values = reportValues(Profile("ישראל ישראלי", "123456789", "קרני שומרון", "מדריך", "חדר שלווה"),
            YearMonth.of(2026, 10), days, "120", LocalDate.of(2026, 11, 1), zone)
        val out = ByteArrayOutputStream()
        DocxFiller.fill(ByteArrayInputStream(template), values, out)
        System.getProperty("docxOut")?.let { File(it).writeBytes(out.toByteArray()) }

        val names = mutableListOf<String>()
        var xml = ""
        ZipInputStream(ByteArrayInputStream(out.toByteArray())).use { z ->
            while (true) {
                val e = z.nextEntry ?: break
                names += e.name
                val b = z.readBytes()
                if (e.name == "word/document.xml") xml = b.toString(Charsets.UTF_8)
            }
        }
        assertTrue(names.contains("word/media/image1.jpeg"))
        assertFalse(xml.contains("{{"))
        assertTrue(xml.contains("ישראל ישראלי"))
        assertTrue(xml.contains("לילה &amp; &lt;חירום&gt;"))
        assertTrue(xml.contains("17:40"))
    }

    private fun zipEntries(bytes: ByteArray): Map<String, ByteArray> {
        val out = linkedMapOf<String, ByteArray>()
        ZipInputStream(ByteArrayInputStream(bytes)).use { z ->
            while (true) {
                val e = z.nextEntry ?: break
                out[e.name] = z.readBytes()
            }
        }
        return out
    }

    @Test
    fun addsSignatureWhenSet() {
        val template = File("src/main/assets/report_template.docx").readBytes()
        val values = reportValues(Profile("ישראל ישראלי"), YearMonth.of(2026, 10), emptyList(), "", LocalDate.of(2026, 11, 1), zone)
        val png = System.getProperty("signaturePng")?.let { File(it).readBytes() } ?: byteArrayOf(1, 2, 3)
        val out = ByteArrayOutputStream()
        DocxFiller.fill(ByteArrayInputStream(template), values, out, signaturePng = png)
        System.getProperty("docxSignedOut")?.let { File(it).writeBytes(out.toByteArray()) }

        val parts = zipEntries(out.toByteArray())
        assertTrue(png.contentEquals(parts.getValue("word/media/signature.png")))
        val xml = parts.getValue("word/document.xml").toString(Charsets.UTF_8)
        assertFalse(xml.contains("{{"))
        assertTrue(xml.contains("""r:embed="rIdSignature""""))
        assertTrue(parts.getValue("word/_rels/document.xml.rels").toString(Charsets.UTF_8).contains("""Id="rIdSignature""""))
        assertTrue(parts.getValue("[Content_Types].xml").toString(Charsets.UTF_8).contains("""Extension="png""""))
        // the labels around the signature are untouched
        assertTrue(xml.contains("חתימת העובד/ת"))
        assertTrue(xml.contains("חתימת מנהל"))
    }

    @Test
    fun keepsBlankSignatureLineWithoutSignature() {
        val template = File("src/main/assets/report_template.docx").readBytes()
        val out = ByteArrayOutputStream()
        DocxFiller.fill(ByteArrayInputStream(template), emptyMap(), out)
        val parts = zipEntries(out.toByteArray())
        assertFalse(parts.containsKey("word/media/signature.png"))
        val xml = parts.getValue("word/document.xml").toString(Charsets.UTF_8)
        assertFalse(xml.contains("rIdSignature"))
        assertTrue(xml.contains(" ___________ "))
    }
}
