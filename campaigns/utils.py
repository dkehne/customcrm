from accounts.models import Contact


def get_contacts_for_product(account, campaign_product, phase_id=None):
    """Return the contacts to add to a campaign for a given account and product.

    - No campaign_product: all is_primary=True contacts.
    - Account has only one active product matching campaign_product: fall back to
      all is_primary=True contacts (no explicit assignment required).
    - Account has multiple active products: use AccountProduct.primary_contacts for
      the matching product; skip (return empty) if none are assigned.
    """
    active_aps = account.account_products.filter(is_archived=False)
    if campaign_product is None:
        return account.contacts.filter(is_primary=True, is_archived=False)

    matching_ap = active_aps.filter(product=campaign_product)
    if phase_id:
        matching_ap = matching_ap.filter(current_phase_id=phase_id)
    matching_ap = matching_ap.first()
    if not matching_ap:
        return Contact.objects.none()

    if active_aps.count() == 1:
        return account.contacts.filter(is_primary=True, is_archived=False)

    assigned = matching_ap.primary_contacts.filter(is_primary=True, is_archived=False)
    if not assigned.exists():
        return Contact.objects.none()
    return assigned
