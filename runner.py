import re
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import sync_playwright


def run_browser(urls, submit, confirmation, log, cancelled):
    """One browser, a fresh context for each response; never retry a submission."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
        try:
            count = len(urls)
            for number in range(1, count + 1):
                if cancelled.is_set():
                    return 'cancelled'
                context = browser.new_context(locale='en-US')
                try:
                    page = context.new_page()
                    page.set_default_timeout(15000)
                    page.goto(urls[number - 1], wait_until='domcontentloaded', timeout=45000)
                    if urlsplit(page.url).hostname != 'docs.google.com':
                        raise RuntimeError('Form redirected away from Google Forms. Sign-in forms are unsupported.')
                    heading = page.get_by_role('heading', level=1).first
                    heading.wait_for()
                    if not re.search(r'\bTEST ONLY\b', heading.inner_text(), re.I):
                        raise RuntimeError('Respondent-visible form title must contain TEST ONLY. Use a disposable copy.')
                    log(f'Response {number}/{count}: opened test form.')
                    picked = '; '.join(f"{k.replace('entry.', '')}={' | '.join(v)[:40]}" for k, v in parse_qs(urlsplit(urls[number - 1]).query).items())
                    log(f'Response {number}: answers {picked}')
                    for section in range(1, 51):
                        if cancelled.is_set():
                            return 'cancelled'
                        submit_button = page.get_by_role('button', name='Submit', exact=True)
                        if submit_button.count() and submit_button.first.is_visible():
                            if not submit:
                                log(f'Response {number}: preview reached final page; nothing submitted. Review optional field coverage in Google Forms.')
                                break
                            # Record network acknowledgement and require a confirmation page as well.
                            log(f'Response {number}: submitting once. If confirmation is uncertain the batch stops.')
                            with page.expect_response(lambda r: '/formResponse' in r.url and r.request.method == 'POST', timeout=30000) as ack:
                                submit_button.first.click()
                            response = ack.value
                            if response.status != 200:
                                raise RuntimeError(f'Submission returned HTTP {response.status}; check Google Forms before retrying.')
                            try:
                                page.get_by_text(confirmation, exact=False).first.wait_for(state='visible', timeout=15000)
                                if page.get_by_role('button', name='Submit', exact=True).count():
                                    raise RuntimeError('Submit page still present.')
                            except Exception as exc:
                                raise RuntimeError('Submission outcome uncertain. Check Responses in Google Forms before starting again; no automatic retry.') from exc
                            log(f'Response {number}: confirmed.', completed=True)
                            break
                        next_button = page.get_by_role('button', name='Next', exact=True)
                        if not next_button.count():
                            raise RuntimeError('No Next/Submit button. Check form access, language, CAPTCHA, or sign-in requirements.')
                        before = page.locator('body').inner_text()
                        next_button.first.click()
                        try:
                            page.wait_for_function('old => document.body.innerText !== old', arg=before, timeout=10000)
                        except Exception as exc:
                            raise RuntimeError('Section did not advance. Check required questions and answer validation.') from exc
                        errors = page.locator('[role="alert"]').all_inner_texts()
                        if any(s.strip() for s in errors):
                            raise RuntimeError('Google Forms validation: ' + ' / '.join(errors)[:400])
                    else:
                        raise RuntimeError('More than 50 sections; stopped.')
                finally:
                    context.close()
                if number < count and cancelled.wait(3):
                    return 'cancelled'
            return 'finished'
        finally:
            browser.close()
