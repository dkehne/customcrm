from django import forms
from core.utils import BootstrapFormMixin
from .models import Product, ProductPhase, ProductField, AccountProduct


class ProductForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name']


class ProductPhaseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductPhase
        fields = ['name', 'order', 'is_final_phase']


class ProductFieldForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductField
        fields = ['name', 'field_type', 'show_on_dashboard']


class AccountProductForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AccountProduct
        fields = ['product', 'current_phase']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_archived=False)
        if self.instance and self.instance.pk and self.instance.product_id:
            self.fields['current_phase'].queryset = ProductPhase.objects.filter(product=self.instance.product)
        elif 'product' in self.data:
            try:
                self.fields['current_phase'].queryset = ProductPhase.objects.filter(product_id=int(self.data.get('product')))
            except (ValueError, TypeError):
                self.fields['current_phase'].queryset = ProductPhase.objects.none()
        else:
            self.fields['current_phase'].queryset = ProductPhase.objects.none()
