package com.hourstracker.app.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.view.View
import android.widget.RemoteViews
import com.hourstracker.app.R
import com.hourstracker.app.report.daySummaries
import com.hourstracker.app.report.formatClock
import com.hourstracker.app.report.formatMinutes
import com.hourstracker.app.storage.AppState
import com.hourstracker.app.storage.Store
import com.hourstracker.app.ui.ConfirmActivity
import com.hourstracker.app.ui.MainActivity
import java.time.Instant
import java.time.YearMonth
import java.time.ZoneId

/** Home-screen widget: live timer plus one round start/stop button. The button always asks for confirmation first. */
class TimerWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) {
        Store.init(context)
        val views = buildViews(context, Store.state.value, System.currentTimeMillis())
        ids.forEach { manager.updateAppWidget(it, views) }
    }

    companion object {
        fun updateAll(context: Context) {
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, TimerWidget::class.java))
            if (ids.isEmpty()) return
            val views = buildViews(context, Store.state.value, System.currentTimeMillis())
            ids.forEach { manager.updateAppWidget(it, views) }
        }

        internal fun buildViews(context: Context, state: AppState, now: Long): RemoteViews {
            val running = state.running
            val today = Instant.ofEpochMilli(now).atZone(ZoneId.systemDefault()).toLocalDate()
            val days = daySummaries(state.sessions, YearMonth.from(today))
            val todayMinutes = days.firstOrNull { it.date == today }?.totalMinutes(now) ?: 0L
            val monthMinutes = days.sumOf { it.totalMinutes(now) }

            val views = RemoteViews(context.packageName, R.layout.widget_timer)
            views.setTextViewText(R.id.widget_month_total, "החודש ${formatMinutes(monthMinutes)} · ${days.size} ימי עבודה")
            if (running != null) {
                views.setInt(R.id.widget_root, "setBackgroundResource", R.drawable.widget_bg_running)
                views.setTextViewText(R.id.widget_status, "● במשמרת מאז ${formatClock(running.start)}")
                views.setViewVisibility(R.id.widget_chrono, View.VISIBLE)
                views.setViewVisibility(R.id.widget_today, View.GONE)
                views.setChronometer(R.id.widget_chrono, SystemClock.elapsedRealtime() - (now - running.start), null, true)
                views.setInt(R.id.widget_button_circle, "setBackgroundResource", R.drawable.widget_button_stop)
                views.setImageViewResource(R.id.widget_button_icon, R.drawable.ic_stop)
                views.setTextViewText(R.id.widget_button_label, "סיום")
            } else {
                views.setInt(R.id.widget_root, "setBackgroundResource", R.drawable.widget_bg)
                views.setTextViewText(R.id.widget_status, "לא במשמרת")
                views.setViewVisibility(R.id.widget_chrono, View.GONE)
                views.setViewVisibility(R.id.widget_today, View.VISIBLE)
                views.setChronometer(R.id.widget_chrono, SystemClock.elapsedRealtime(), null, false)
                views.setTextViewText(R.id.widget_today, "היום ${formatMinutes(todayMinutes)}")
                views.setInt(R.id.widget_button_circle, "setBackgroundResource", R.drawable.widget_button_start)
                views.setImageViewResource(R.id.widget_button_icon, R.drawable.ic_play)
                views.setTextViewText(R.id.widget_button_label, "התחלה")
            }

            val confirm = PendingIntent.getActivity(
                context, 1,
                Intent(context, ConfirmActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            val openApp = PendingIntent.getActivity(
                context, 2,
                Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            views.setOnClickPendingIntent(R.id.widget_button, confirm)
            views.setOnClickPendingIntent(R.id.widget_info, openApp)
            return views
        }
    }
}
