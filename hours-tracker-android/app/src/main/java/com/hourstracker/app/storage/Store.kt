package com.hourstracker.app.storage

import android.content.Context
import com.hourstracker.app.report.Profile
import com.hourstracker.app.report.WorkSession
import com.hourstracker.app.report.roundToFiveMinutes
import com.hourstracker.app.widget.TimerWidget
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.YearMonth

data class AppState(
    val sessions: List<WorkSession> = emptyList(),
    /** Free text for "סה״כ נסיעות", keyed by "yyyy-MM". */
    val travel: Map<String, String> = emptyMap(),
    /** Months for which a Word report was created, keyed by "yyyy-MM". */
    val exported: Set<String> = emptySet(),
    val profile: Profile = Profile(),
) {
    val running: WorkSession? get() = sessions.firstOrNull { it.isRunning }
}

fun YearMonth.key(): String = toString()

/**
 * Single source of truth for the app and the widget. Everything is kept in one small JSON file
 * (included in Android's automatic backup).
 */
object Store {
    private lateinit var appContext: Context
    private lateinit var file: File
    private val _state = MutableStateFlow(AppState())
    val state: StateFlow<AppState> get() = _state

    @Synchronized
    fun init(context: Context) {
        if (::file.isInitialized) return
        appContext = context.applicationContext
        file = File(appContext.filesDir, "hours.json")
        _state.value = load()
    }

    /** Starts a shift at [at] (the moment the button was pressed), rounded to 5 minutes. */
    fun startNow(at: Long = System.currentTimeMillis()): WorkSession? = mutate { s ->
        if (s.running != null) s
        else s.copy(sessions = s.sessions + WorkSession(newId(s), roundToFiveMinutes(at), null))
    }.running

    /** Stops the running session and returns it (finished), or null if nothing was running. */
    fun stopNow(note: String = "", at: Long = System.currentTimeMillis()): WorkSession? {
        var stopped: WorkSession? = null
        mutate { s ->
            val running = s.running ?: return@mutate s
            val done = running.copy(end = maxOf(roundToFiveMinutes(at), running.start), note = note.trim().ifEmpty { running.note })
            stopped = done
            s.copy(sessions = s.sessions.map { if (it.id == running.id) done else it })
        }
        return stopped
    }

    fun upsert(session: WorkSession) = mutate { s ->
        val exists = s.sessions.any { it.id == session.id }
        val list = if (exists) s.sessions.map { if (it.id == session.id) session else it }
        else s.sessions + session.copy(id = newId(s))
        s.copy(sessions = list.sortedBy { it.start })
    }

    fun delete(id: Long) = mutate { s -> s.copy(sessions = s.sessions.filterNot { it.id == id }) }

    fun setTravel(month: YearMonth, text: String) = mutate { s -> s.copy(travel = s.travel + (month.key() to text)) }

    fun markExported(month: YearMonth) = mutate { s -> s.copy(exported = s.exported + month.key()) }

    fun setProfile(profile: Profile) = mutate { s -> s.copy(profile = profile) }

    private fun newId(s: AppState): Long = (s.sessions.maxOfOrNull { it.id } ?: 0L) + 1

    @Synchronized
    private fun mutate(change: (AppState) -> AppState): AppState {
        val old = _state.value
        val new = change(old)
        if (new != old) {
            _state.value = new
            save(new)
            TimerWidget.updateAll(appContext)
        }
        return new
    }

    private fun load(): AppState {
        if (!file.exists()) return AppState()
        return try {
            val root = JSONObject(file.readText())
            val sessions = root.optJSONArray("sessions") ?: JSONArray()
            val list = (0 until sessions.length()).map { i ->
                val o = sessions.getJSONObject(i)
                WorkSession(
                    id = o.getLong("id"),
                    start = o.getLong("start"),
                    end = if (o.isNull("end")) null else o.getLong("end"),
                    note = o.optString("note"),
                )
            }
            val travel = root.optJSONObject("travel")?.let { t -> t.keys().asSequence().associateWith { t.getString(it) } }
            val exported = root.optJSONArray("exported")?.let { a -> (0 until a.length()).map { a.getString(it) }.toSet() }
            val p = root.optJSONObject("profile")
            AppState(
                sessions = list.sortedBy { it.start },
                travel = travel ?: emptyMap(),
                exported = exported ?: emptySet(),
                profile = Profile(
                    name = p?.optString("name").orEmpty(),
                    idNumber = p?.optString("idNumber").orEmpty(),
                    address = p?.optString("address").orEmpty(),
                    role = p?.optString("role").orEmpty(),
                    workplace = p?.optString("workplace").orEmpty(),
                ),
            )
        } catch (e: Exception) {
            // Keep the unreadable file aside instead of overwriting it.
            file.copyTo(File(file.parentFile, "hours.broken.${System.currentTimeMillis()}.json"), overwrite = true)
            AppState()
        }
    }

    private fun save(s: AppState) {
        val root = JSONObject()
        root.put("sessions", JSONArray().apply {
            s.sessions.forEach { w ->
                put(JSONObject().apply {
                    put("id", w.id)
                    put("start", w.start)
                    put("end", w.end ?: JSONObject.NULL)
                    put("note", w.note)
                })
            }
        })
        root.put("travel", JSONObject().apply { s.travel.forEach { (k, v) -> put(k, v) } })
        root.put("exported", JSONArray().apply { s.exported.forEach { put(it) } })
        root.put("profile", JSONObject().apply {
            put("name", s.profile.name)
            put("idNumber", s.profile.idNumber)
            put("address", s.profile.address)
            put("role", s.profile.role)
            put("workplace", s.profile.workplace)
        })
        val tmp = File(file.parentFile, "hours.json.tmp")
        tmp.writeText(root.toString())
        if (!tmp.renameTo(file)) {
            file.writeText(root.toString())
            tmp.delete()
        }
    }
}
