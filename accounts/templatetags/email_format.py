import re

from django import template
from django.utils.html import escape, urlize
from django.utils.safestring import mark_safe

register = template.Library()


def _parse_sf_email(text):
    """Parse a Salesforce email description into header fields and body."""
    result = {'recipients': '', 'cc': '', 'attachments': '', 'subject': '', 'body': ''}

    # Extract body after " Text: "
    text_match = re.split(r'\s{2}Thema:\s*', text, maxsplit=1)
    if len(text_match) == 2:
        header_part = text_match[0]
        rest = text_match[1]

        # Extract subject and body from rest
        body_match = re.split(r'\s*Text:\s*', rest, maxsplit=1)
        if len(body_match) == 2:
            result['subject'] = body_match[0].strip()
            result['body'] = body_match[1].strip()
        else:
            result['body'] = rest.strip()

        # Parse header fields
        cc_match = re.split(r'\s*CC:\s*', header_part, maxsplit=1)
        if len(cc_match) == 2:
            result['recipients'] = cc_match[0].replace('Weitere Empfänger:', '').strip()
            bcc_rest = cc_match[1]
            bcc_match = re.split(r'\s*BCC:\s*', bcc_rest, maxsplit=1)
            if len(bcc_match) == 2:
                result['cc'] = bcc_match[0].strip()
                att_rest = bcc_match[1]
                att_match = re.split(r'\s*Anhang:\s*', att_rest, maxsplit=1)
                if len(att_match) == 2:
                    result['attachments'] = att_match[1].strip()
    else:
        # Fallback: couldn't parse, return raw text as body
        result['body'] = text

    return result


@register.filter(name='format_email')
def format_email(description):
    """Format a Salesforce email activity description as structured HTML."""
    if not description:
        return ''

    parsed = _parse_sf_email(description)

    # Build header
    header_lines = []
    if parsed['recipients']:
        escaped = escape(parsed['recipients'])
        header_lines.append(f'<strong>An:</strong> {escaped}')
    if parsed['cc']:
        escaped = escape(parsed['cc'])
        header_lines.append(f'<strong>CC:</strong> {escaped}')
    if parsed['attachments']:
        escaped = escape(parsed['attachments'])
        header_lines.append(f'<strong>Anhänge:</strong> {escaped}')

    # Build body — convert double-space line breaks, then urlize
    body = parsed['body']
    body = escape(body)
    # Salesforce uses double spaces for line breaks
    body = re.sub(r'  +', '<br>', body)
    # Make URLs clickable
    body = urlize(body)

    parts = []
    if parsed['subject']:
        subj = escape(parsed['subject'])
        parts.append(
            f'<div class="d-flex align-items-center gap-2 mb-2">'
            f'<i class="bi bi-envelope text-muted"></i>'
            f'<strong>{subj}</strong></div>'
        )
    if header_lines:
        meta = '<br>'.join(header_lines)
        parts.append(f'<div class="text-muted small mb-2">{meta}</div>')
    if header_lines or parsed['subject']:
        parts.append('<hr class="my-2">')
    parts.append(f'<div class="email-body-text">{body}</div>')

    return mark_safe(''.join(parts))


@register.filter(name='pct_of')
def pct_of(value, total):
    """Return value as percentage of total, rounded to 0 decimals. Returns '' if total is 0."""
    try:
        total = int(total)
        if total == 0:
            return ''
        return f'{int(value) / total * 100:.0f}'
    except (TypeError, ValueError, ZeroDivisionError):
        return ''
