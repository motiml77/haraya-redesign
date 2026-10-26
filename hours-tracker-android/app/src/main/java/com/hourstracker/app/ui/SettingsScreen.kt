package com.hourstracker.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.hourstracker.app.export.ReportExporter
import com.hourstracker.app.report.Profile

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(profile: Profile, onSave: (Profile) -> Unit, onBack: () -> Unit) {
    var name by rememberSaveable { mutableStateOf(profile.name) }
    var idNumber by rememberSaveable { mutableStateOf(profile.idNumber) }
    var address by rememberSaveable { mutableStateOf(profile.address) }
    var role by rememberSaveable { mutableStateOf(profile.role) }
    var workplace by rememberSaveable { mutableStateOf(profile.workplace) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("פרטי העובד") },
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
                "הפרטים האלה ממולאים בראש טופס ה-Word של כל חודש.",
                style = MaterialTheme.typography.bodyMedium,
            )
            Field("שם העובד", name) { name = it }
            Field("ת״ז", idNumber, KeyboardType.Number) { idNumber = it }
            Field("כתובת מגורים", address) { address = it }
            Field("תפקיד", role) { role = it }
            Field("מקום עבודה", workplace) { workplace = it }
            Button(
                onClick = { onSave(Profile(name.trim(), idNumber.trim(), address.trim(), role.trim(), workplace.trim())) },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("שמירה") }
            Text(
                "הדוחות נשמרים בטלפון בתיקייה: Documents/${ReportExporter.FOLDER}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun Field(label: String, value: String, keyboard: KeyboardType = KeyboardType.Text, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
        modifier = Modifier.fillMaxWidth(),
    )
}
