package com.hourstracker.app

import android.app.Application
import com.hourstracker.app.storage.Store

class HoursApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Store.init(this)
    }
}
