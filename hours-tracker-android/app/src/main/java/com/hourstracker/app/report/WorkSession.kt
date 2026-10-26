package com.hourstracker.app.report

/** One work interval. [end] is null while the timer is still running. Times are epoch millis. */
data class WorkSession(
    val id: Long,
    val start: Long,
    val end: Long?,
    val note: String = "",
) {
    val isRunning: Boolean get() = end == null

    /** Whole minutes worked, rounded to the nearest minute. Running sessions count up to [now]. */
    fun minutes(now: Long = System.currentTimeMillis()): Long {
        val stop = end ?: now
        return ((stop - start).coerceAtLeast(0) + 30_000) / 60_000
    }
}

/** Employee details printed at the top of the form. */
data class Profile(
    val name: String = "",
    val idNumber: String = "",
    val address: String = "",
    val role: String = "",
    val workplace: String = "",
)
