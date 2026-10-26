package com.hourstracker.app.report

import java.io.InputStream
import java.io.OutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

/**
 * Fills a .docx whose word/document.xml contains {{KEY}} placeholders (each inside a single run).
 * Unknown placeholders are replaced with an empty string. Every other part of the package is copied as is.
 */
object DocxFiller {
    private val PLACEHOLDER = Regex("""\{\{([A-Z_0-9]+)\}\}""")

    fun fill(template: InputStream, values: Map<String, String>, out: OutputStream) {
        val zin = ZipInputStream(template)
        val zout = ZipOutputStream(out)
        while (true) {
            val entry = zin.nextEntry ?: break
            var bytes = zin.readBytes()
            if (entry.name == "word/document.xml") {
                bytes = fillXml(bytes.toString(Charsets.UTF_8), values).toByteArray(Charsets.UTF_8)
            }
            zout.putNextEntry(ZipEntry(entry.name))
            zout.write(bytes)
            zout.closeEntry()
        }
        zout.finish()
    }

    fun fillXml(xml: String, values: Map<String, String>): String =
        PLACEHOLDER.replace(xml) { m -> escape(values[m.groupValues[1]].orEmpty()) }

    private fun escape(s: String): String = buildString {
        for (c in s) {
            when (c) {
                '&' -> append("&amp;")
                '<' -> append("&lt;")
                '>' -> append("&gt;")
                '"' -> append("&quot;")
                '\n', '\r', '\t' -> append(' ')
                else -> if (c >= ' ') append(c)
            }
        }
    }
}
