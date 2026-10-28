package com.hourstracker.app.report

import java.io.InputStream
import java.io.OutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

/**
 * Fills a .docx whose word/document.xml contains {{KEY}} placeholders (each inside a single run).
 * Unknown placeholders are replaced with an empty string. Every other part of the package is copied as is.
 *
 * {{SIGNATURE}} is special: with a [signaturePng] the whole run becomes an inline picture of the signature,
 * without one it turns back into the blank signature line.
 */
object DocxFiller {
    private val PLACEHOLDER = Regex("""\{\{([A-Z_0-9]+)\}\}""")
    private val SIGNATURE_RUN = Regex("""<w:r(?:\s[^>]*)?>(?:(?!</w:r>).)*\{\{SIGNATURE\}\}.*?</w:r>""", RegexOption.DOT_MATCHES_ALL)

    private const val SIGNATURE_PART = "word/media/signature.png"
    private const val SIGNATURE_REL_ID = "rIdSignature"
    private const val BLANK_SIGNATURE_LINE = " ___________                   "

    // 78 x 26 pt, matching the 3:1 shape of the drawn signature; lowered 3.5 pt so its baseline sits on the form's line.
    private const val SIGNATURE_WIDTH_EMU = 990_600
    private const val SIGNATURE_HEIGHT_EMU = 330_200
    private const val RUN_PROPS =
        """<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:b/><w:bCs/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl/>"""

    private const val SIGNATURE_RUNS =
        """<w:r><w:rPr><w:noProof/><w:position w:val="-7"/></w:rPr><w:drawing>""" +
            """<wp:inline distT="0" distB="0" distL="0" distR="0">""" +
            """<wp:extent cx="$SIGNATURE_WIDTH_EMU" cy="$SIGNATURE_HEIGHT_EMU"/>""" +
            """<wp:docPr id="9001" name="חתימת העובד"/>""" +
            """<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>""" +
            """<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">""" +
            """<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">""" +
            """<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">""" +
            """<pic:nvPicPr><pic:cNvPr id="0" name="signature.png"/><pic:cNvPicPr/></pic:nvPicPr>""" +
            """<pic:blipFill><a:blip r:embed="$SIGNATURE_REL_ID"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>""" +
            """<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="$SIGNATURE_WIDTH_EMU" cy="$SIGNATURE_HEIGHT_EMU"/></a:xfrm>""" +
            """<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>""" +
            """</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>""" +
            """<w:r><w:rPr>$RUN_PROPS</w:rPr><w:t xml:space="preserve">        </w:t></w:r>"""

    fun fill(template: InputStream, values: Map<String, String>, out: OutputStream, signaturePng: ByteArray? = null) {
        val zin = ZipInputStream(template)
        val zout = ZipOutputStream(out)
        while (true) {
            val entry = zin.nextEntry ?: break
            var bytes = zin.readBytes()
            when (entry.name) {
                "word/document.xml" ->
                    bytes = fillXml(bytes.toString(Charsets.UTF_8), values, signaturePng != null).toByteArray(Charsets.UTF_8)
                "word/_rels/document.xml.rels" ->
                    if (signaturePng != null) bytes = addSignatureRelationship(bytes.toString(Charsets.UTF_8)).toByteArray(Charsets.UTF_8)
                "[Content_Types].xml" ->
                    if (signaturePng != null) bytes = addPngContentType(bytes.toString(Charsets.UTF_8)).toByteArray(Charsets.UTF_8)
            }
            zout.putNextEntry(ZipEntry(entry.name))
            zout.write(bytes)
            zout.closeEntry()
        }
        if (signaturePng != null) {
            zout.putNextEntry(ZipEntry(SIGNATURE_PART))
            zout.write(signaturePng)
            zout.closeEntry()
        }
        zout.finish()
    }

    fun fillXml(xml: String, values: Map<String, String>, withSignature: Boolean = false): String {
        val signed =
            if (withSignature) SIGNATURE_RUN.replace(xml) { SIGNATURE_RUNS }
            else xml.replace("{{SIGNATURE}}", BLANK_SIGNATURE_LINE)
        return PLACEHOLDER.replace(signed) { m -> escape(values[m.groupValues[1]].orEmpty()) }
    }

    private fun addSignatureRelationship(rels: String): String {
        val rel = """<Relationship Id="$SIGNATURE_REL_ID" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/signature.png"/>"""
        return rels.replace("</Relationships>", "$rel</Relationships>")
    }

    private fun addPngContentType(types: String): String =
        if (types.contains("""Extension="png"""")) types
        else types.replaceFirst(Regex("""(<Types[^>]*>)"""), """$1<Default Extension="png" ContentType="image/png"/>""")

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
