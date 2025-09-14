# main_app/forms.py
from django import forms
from .models import Job, Attachment


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ["machine", "material", "stock_lwh_mm", "qty", "wcs", "status"]

    def clean_qty(self):
        qty = self.cleaned_data.get("qty")
        if qty is not None and qty <= 0:
            raise forms.ValidationError("Quantity must be positive.")
        return qty

    def clean_stock_lwh_mm(self):
        stock = self.cleaned_data.get("stock_lwh_mm") or {}
        L = float(stock.get("L", 0) or 0)
        W = float(stock.get("W", 0) or 0)
        H = float(stock.get("H", 0) or 0)
        if L <= 0 or W <= 0 or H <= 0:
            raise forms.ValidationError("Stock dimensions must all be positive.")
        return stock

    def clean_wcs(self):
        wcs = self.cleaned_data.get("wcs", "").upper()
        if wcs not in {"G54", "G55", "G56", "G57", "G58", "G59"}:
            raise forms.ValidationError("WCS must be one of G54–G59.")
        return wcs


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["file"]

    def clean_file(self):
        file = self.cleaned_data.get("file")
        if file and file.size > 10 * 1024 * 1024:  # 10 MB limit
            raise forms.ValidationError("Attachment file is too large (max 10MB).")
        return file