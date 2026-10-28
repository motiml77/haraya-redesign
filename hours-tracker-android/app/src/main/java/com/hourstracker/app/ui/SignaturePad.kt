package com.hourstracker.app.ui

import android.graphics.Bitmap
import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.clickable
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import java.io.ByteArrayOutputStream

class PenColor(val label: String, val color: Color)

val PEN_COLORS = listOf(
    PenColor("כחול", Color(0xFF1A3A8F)),
    PenColor("שחור", Color(0xFF111111)),
    PenColor("ירוק", Color(0xFF14A56B)),
)

/** A signature is a few strokes, each a list of touch points. */
typealias Strokes = List<List<Offset>>

// Everything is expressed relative to the pad width, so the pad on screen and the picture in the Word form look the same.
private const val PEN_WIDTH = 0.012f
private const val LINE_WIDTH = 0.006f
private const val BASELINE_Y = 0.88f // fraction of the pad height; also the guide line the user signs on
const val SIGNATURE_ASPECT = 3f
private const val OUT_WIDTH = 900
private const val OUT_HEIGHT = OUT_WIDTH / 3

/** Draws [strokes] (in a pad of [padWidth] px) on a transparent 900x300 PNG, with the form's signature line under them. */
fun renderSignaturePng(strokes: Strokes, padWidth: Float, color: Color): ByteArray {
    val scale = OUT_WIDTH / padWidth
    val bitmap = Bitmap.createBitmap(OUT_WIDTH, OUT_HEIGHT, Bitmap.Config.ARGB_8888)
    val canvas = android.graphics.Canvas(bitmap)
    val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        this.color = color.toArgb()
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
        strokeWidth = OUT_WIDTH * PEN_WIDTH
    }
    for (points in strokes) {
        if (points.size == 1) {
            canvas.drawPoint(points[0].x * scale, points[0].y * scale, paint)
            continue
        }
        val path = android.graphics.Path()
        path.moveTo(points[0].x * scale, points[0].y * scale)
        for (i in 1 until points.size) {
            val prev = points[i - 1]
            val cur = points[i]
            path.quadTo(prev.x * scale, prev.y * scale, (prev.x + cur.x) / 2 * scale, (prev.y + cur.y) / 2 * scale)
        }
        path.lineTo(points.last().x * scale, points.last().y * scale)
        canvas.drawPath(path, paint)
    }
    paint.strokeWidth = OUT_WIDTH * LINE_WIDTH
    canvas.drawLine(OUT_WIDTH * 0.02f, OUT_HEIGHT * BASELINE_Y, OUT_WIDTH * 0.98f, OUT_HEIGHT * BASELINE_Y, paint)
    return ByteArrayOutputStream().also { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray()
}

private fun DrawScope.drawStroke(points: List<Offset>, color: Color) {
    val width = size.width * PEN_WIDTH
    if (points.size == 1) {
        drawCircle(color, radius = width / 2, center = points[0])
        return
    }
    val path = Path().apply {
        moveTo(points[0].x, points[0].y)
        for (i in 1 until points.size) {
            val prev = points[i - 1]
            val cur = points[i]
            quadraticTo(prev.x, prev.y, (prev.x + cur.x) / 2, (prev.y + cur.y) / 2)
        }
        lineTo(points.last().x, points.last().y)
    }
    drawPath(path, color, style = Stroke(width = width, cap = StrokeCap.Round, join = StrokeJoin.Round))
}

/**
 * The signature screen: a pad to draw on, pen colour, clear, cancel, save.
 * [initialStrokes] only exists so screenshots can show a finished signature.
 */
@Composable
fun SignaturePadContent(
    onSave: (png: ByteArray) -> Unit,
    onCancel: () -> Unit,
    initialStrokes: Strokes = emptyList(),
) {
    val strokes = remember { mutableStateListOf<List<Offset>>().apply { addAll(initialStrokes) } }
    var current by remember { mutableStateOf<List<Offset>>(emptyList()) }
    var penColor by remember { mutableStateOf(PEN_COLORS[0]) }
    var padSize by remember { mutableStateOf(IntSize.Zero) }

    fun finishStroke() {
        if (current.isNotEmpty()) strokes.add(current)
        current = emptyList()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("חתימה לטופס", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(
            "חתמו באצבע על הקו. החתימה תתווסף אוטומטית בשורת \"חתימת העובד/ת\" בכל טופס.",
            style = MaterialTheme.typography.bodyMedium,
        )

        Canvas(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(SIGNATURE_ASPECT)
                .background(Color.White, RoundedCornerShape(16.dp))
                .border(1.dp, Color(0xFFD0D9E4), RoundedCornerShape(16.dp))
                .onSizeChanged { padSize = it }
                .pointerInput(Unit) {
                    detectDragGestures(
                        onDragStart = { current = listOf(it) },
                        onDrag = { change, _ ->
                            change.consume()
                            current = current + change.position
                        },
                        onDragEnd = { finishStroke() },
                        onDragCancel = { finishStroke() },
                    )
                },
        ) {
            val y = size.height * BASELINE_Y
            drawLine(Color(0xFFB8C2CF), Offset(size.width * 0.02f, y), Offset(size.width * 0.98f, y), strokeWidth = size.width * LINE_WIDTH)
            strokes.forEach { drawStroke(it, penColor.color) }
            if (current.isNotEmpty()) drawStroke(current, penColor.color)
        }

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("צבע העט", style = MaterialTheme.typography.titleSmall)
            PEN_COLORS.forEach { pen ->
                val selected = pen === penColor
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .clickable { penColor = pen }
                        .border(if (selected) 3.dp else 1.dp, if (selected) Navy else Color(0xFFD0D9E4), CircleShape)
                        .padding(6.dp)
                        .background(pen.color, CircleShape),
                )
            }
            Spacer(Modifier.weight(1f))
            OutlinedButton(onClick = { strokes.clear(); current = emptyList() }, enabled = strokes.isNotEmpty()) { Text("ניקוי") }
        }

        Spacer(Modifier.weight(1f))

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            TextButton(onClick = onCancel, modifier = Modifier
                .weight(1f)
                .height(56.dp)) { Text("ביטול", fontWeight = FontWeight.Bold) }
            Button(
                onClick = { onSave(renderSignaturePng(strokes.toList(), padSize.width.toFloat(), penColor.color)) },
                enabled = strokes.isNotEmpty() && padSize.width > 0,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier
                    .weight(2f)
                    .height(56.dp),
            ) { Text("שמירת החתימה", fontWeight = FontWeight.Bold) }
        }
    }
}
