from django.contrib import admin

from .models import Order, Portfolio, PortfolioSnapshot, Position


class PositionInline(admin.TabularInline):
    model = Position
    extra = 0


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("name", "broker", "is_paper", "initial_capital", "cash")
    list_filter = ("broker", "is_paper")
    inlines = [PositionInline]


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "stock", "quantity", "average_cost", "current_price")
    list_filter = ("portfolio",)
    search_fields = ("stock__symbol",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "stock", "side", "quantity", "status", "filled_price", "created_at")
    list_filter = ("status", "side", "portfolio")
    search_fields = ("stock__symbol", "broker_order_id")


@admin.register(PortfolioSnapshot)
class PortfolioSnapshotAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "date", "cash", "market_value", "total_value")
    list_filter = ("portfolio",)
    date_hierarchy = "date"
