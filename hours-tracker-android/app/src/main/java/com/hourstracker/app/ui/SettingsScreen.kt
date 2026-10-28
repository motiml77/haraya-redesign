package com.hourstracker.app.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.TextButton
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.hourstracker.app.report.Profile

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    profile: Profile,
    signature: ByteArray?,
    onSignatureSaved: (ByteArray) -> Unit,
    onSignatureCleared: () -> Unit,
    onSave: (Profile) -> Unit,
    onBack: () -> Unit,
) {
    var name by rememberSaveable { mutableStateOf(profile.name) }
    var idNumber by rememberSaveable { mutableStateOf(profile.idNumber) }
    var address by rememberSaveable { mutableStateOf(profile.address) }
    var role by rememberSaveable { mutableStateOf(profile.role) }
    var workplace by rememberSaveable { mutableStateOf(profile.workplace) }
    var drawingSignature by rememberSaveable { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("פרטים בטופס", fontWeight = androidx.compose.ui.text.font.FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "חזרה") }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Navy,
                    titleContentColor = Color.White,
                    navigationIconContentColor = Color.White,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "מה שתכתבו כאן יירשם בראש טופס ה-Word של כל חודש. אפשר לשנות בכל זמן, והשינוי ייכנס לטופס הבא שתיצרו.",
                style = MaterialTheme.typography.bodyMedium,
            )
            Field("שם העובד", name, hint = "למשל: ישראל ישראלי") { name = it }
            Field("ת״ז", idNumber, KeyboardType.Number, hint = "9 ספרות") { idNumber = it }
            Field("כתובת מגורים", address, hint = "רחוב, מספר, יישוב") { address = it }
            Field("תפקיד", role, hint = "למשל: מדריך/ה") { role = it }
            Field("מקום עבודה / בית ספר", workplace, hint = "שם בית הספר או המוסד") { workplace = it }
            SignatureCard(
                signature = signature,
                onDraw = { drawingSignature = true },
                onClear = onSignatureCleared,
            )
            Button(
                onClick = { onSave(Profile(name.trim(), idNumber.trim(), address.trim(), role.trim(), workplace.trim())) },
                shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
            ) { Text("שמירה", fontSize = 18.sp) }
            Text(
                "הטפסים נשמרים בתיקיית ההורדות (Download) בטלפון.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }

    if (drawingSignature) {
        Dialog(
            onDismissRequest = { drawingSignature = false },
            properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false),
        ) {
            SignaturePadContent(
                onSave = { onSignatureSaved(it); drawingSignature = false },
                onCancel = { drawingSignature = false },
            )
        }
    }
}

@Composable
private fun SignatureCard(signature: ByteArray?, onDraw: () -> Unit, onClear: () -> Unit) {
    val image = remember(signature) { signature?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() } }
    Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("חתימה", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Box(
                Modifier
                    .fillMaxWidth()
                    .height(96.dp)
                    .background(MaterialTheme.colorScheme.background, RoundedCornerShape(12.dp)),
                contentAlignment = Alignment.Center,
            ) {
                if (image != null) {
                    Image(image, contentDescription = "החתימה שלך", modifier = Modifier.height(84.dp))
                } else {
                    Text("עוד לא הוגדרה חתימה", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Text(
                if (image != null) "החתימה תתווסף אוטומטית בשורת \"חתימת העובד/ת\" בכל טופס שתיצרו."
                else "אחרי שתחתמו כאן, החתימה תתווסף אוטומטית לכל טופס. אפשר גם להשאיר ריק ולחתום בכתב יד.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onDraw, modifier = Modifier.weight(1f)) {
                    Text(if (image != null) "חתימה מחדש" else "ציור חתימה")
                }
                if (image != null) TextButton(onClick = onClear) { Text("מחיקה", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
private fun Field(
    label: String,
    value: String,
    keyboard: KeyboardType = KeyboardType.Text,
    hint: String = "",
    onChange: (String) -> Unit,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        placeholder = { Text(hint) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
        modifier = Modifier.fillMaxWidth(),
    )
}
