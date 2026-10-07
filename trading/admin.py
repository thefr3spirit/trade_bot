from django.contrib import admin

from .models import MomentumScore, PriceData, RebalanceEvent, Stock, TradingSignal


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "exchange", "sector", "is_active")
    list_filter = ("is_active", "exchange", "sector")
    search_fields = ("symbol", "name")


@admin.register(PriceData)
class PriceDataAdmin(admin.ModelAdmin):
    list_display = ("stock", "date", "open", "high", "low", "close", "volume")
    list_filter = ("stock",)
    search_fields = ("stock__symbol",)
    date_hierarchy = "date"


@admin.register(MomentumScore)
class MomentumScoreAdmin(admin.ModelAdmin):
    list_display = ("stock", "date", "score", "rank")
    list_filter = ("date",)
    search_fields = ("stock__symbol",)


@admin.register(TradingSignal)
class TradingSignalAdmin(admin.ModelAdmin):
    list_display = ("stock", "signal_type", "target_weight", "executed", "created_at")
    list_filter = ("signal_type", "executed")
    search_fields = ("stock__symbol",)


@admin.register(RebalanceEvent)
class RebalanceEventAdmin(admin.ModelAdmin):
    list_display = ("date", "status", "top_n", "num_buys", "num_sells", "completed_at")
    list_filter = ("status",)
