package com.hourstracker.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection

val Navy = Color(0xFF1E3A5F)
val NavyLight = Color(0xFF2E5E8C)
val Green = Color(0xFF2EA66B)
val GreenDark = Color(0xFF0F5132)
val Red = Color(0xFFD9534F)

private val colors = lightColorScheme(
    primary = Navy,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD6E4F5),
    onPrimaryContainer = Navy,
    secondary = Green,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD5F2E3),
    onSecondaryContainer = GreenDark,
    tertiaryContainer = Color(0xFFFFF1D6),
    onTertiaryContainer = Color(0xFF6B4A00),
    error = Red,
    background = Color(0xFFF4F6FA),
    surface = Color(0xFFF4F6FA),
    surfaceContainerLow = Color.White,
    surfaceContainer = Color.White,
    surfaceContainerHigh = Color.White,
)

/** App theme; the whole UI is always right-to-left (Hebrew), whatever the phone's language. */
@Composable
fun HoursTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = colors) {
        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl, content = content)
    }
}
