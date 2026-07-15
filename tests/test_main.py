import unittest
from unittest.mock import patch

import main


class FakeEngine:
    def __init__(self, result: bool = True):
        self.result = result
        self.calls: list[dict[str, object]] = []

    def apply_to_job(self, form_url: str, user_data: dict, cover_letter: str) -> bool:
        self.calls.append(
            {
                "form_url": form_url,
                "user_data": user_data,
                "cover_letter": cover_letter,
            }
        )
        return self.result


class ProcessJobTests(unittest.TestCase):
    @patch("main.bot_telegram.send_alert")
    @patch("main.get_today_stats", return_value=4)
    @patch("main.save_job")
    @patch("main.generate_cover_letter", return_value="Cover letter")
    @patch("main.match_job", return_value=True)
    @patch("main.is_job_applied", return_value=False)
    def test_process_job_runs_shared_application_pipeline(
        self,
        is_job_applied,
        match_job,
        generate_cover_letter,
        save_job,
        get_today_stats,
        send_alert,
    ):
        engine = FakeEngine()
        resume = {"skills": ["Python"]}
        user_data = {"email": "applicant@example.com"}
        job_info = {"job_title": "Engineer", "company": "Example"}

        result = main._process_job(
            engine,
            resume,
            user_data,
            job_info,
            fallback_url="https://example.com/apply",
            source="Web3 Jobs API",
        )

        self.assertTrue(result)
        is_job_applied.assert_called_once_with("https://example.com/apply")
        match_job.assert_called_once_with(job_info, resume)
        generate_cover_letter.assert_called_once_with(job_info, resume)
        save_job.assert_called_once_with(
            "Engineer",
            "Example",
            "https://example.com/apply",
        )
        get_today_stats.assert_called_once_with()
        send_alert.assert_called_once()
        self.assertEqual(
            engine.calls,
            [
                {
                    "form_url": "https://example.com/apply",
                    "user_data": user_data,
                    "cover_letter": "Cover letter",
                }
            ],
        )

    @patch("main.match_job")
    @patch("main.is_job_applied", return_value=True)
    def test_process_job_skips_previously_applied_job(
        self,
        is_job_applied,
        match_job,
    ):
        engine = FakeEngine()

        result = main._process_job(
            engine,
            {},
            {},
            {
                "job_title": "Engineer",
                "company": "Example",
                "application_url": "https://example.com/apply",
            },
        )

        self.assertIsNone(result)
        is_job_applied.assert_called_once_with("https://example.com/apply")
        match_job.assert_not_called()
        self.assertEqual(engine.calls, [])


if __name__ == "__main__":
    unittest.main()
