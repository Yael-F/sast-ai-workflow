import logging
import re
from typing import List

from bs4 import BeautifulSoup

from common.config import Config
from dto.Issue import Issue
from Utils.file_utils import get_google_sheet

logger = logging.getLogger(__name__)


def read_sast_report(config: Config) -> List[Issue]:
    logger.info(f"Reading => {config.INPUT_REPORT_FILE_PATH}")
    if config.INPUT_REPORT_FILE_PATH.startswith("https"):
        return read_sast_report_google_sheet(
            config.SERVICE_ACCOUNT_JSON_PATH, config.INPUT_REPORT_FILE_PATH
        )
    return read_sast_report_local_html(config.INPUT_REPORT_FILE_PATH)


def read_sast_report_google_sheet(service_account_file_path, google_sheet_url) -> List[Issue]:
    """
    Reads a Google Sheet and creates a list of Issue objects based on the 'Finding' column.
    NOTE: Assumes issue details are in the 'Finding'
          column of the first sheet (sheet name doesn't matter).

    :param config: Config object containing configuration details, including:
            - INPUT_REPORT_FILE_PATH: URL of the Google Sheet.
            - SERVICE_ACCOUNT_JSON_PATH: Path to the service account JSON file for authentication.
    :return: List of Issue objects.
    """
    sheet = get_google_sheet(google_sheet_url, service_account_file_path, ignore_error=False)
    rows = sheet.get_all_records()

    # Create a list of Issue objects
    issue_list = []
    for idx, row in enumerate(rows, start=1):
        finding = row.get("Finding")
        if not finding:
            continue

        issue = Issue(f"def{idx}")
        # TODO - please leave a example string for finding
        lines = finding.split("\n")
        issue.issue_type = lines[0].split("Error:")[1].strip().split()[0]
        match = re.search(r"CWE-\d+", lines[0])
        issue.issue_cve = match.group() if match else ""
        issue.issue_cve_link = (
            f"https://cwe.mitre.org/data/definitions/{issue.issue_cve.split('-')[1]}.html"
            if match
            else ""
        )
        issue.trace = "\n".join(lines[1:])
        issue_list.append(issue)

    return issue_list


def read_sast_report_local_html(file_path) -> List[Issue]:
    issue_list = []
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
        all_pre_tags = soup.findAll("pre")
        cur_issue = Issue(-1)
        for tag in all_pre_tags[0].children:
            if tag.name == "a" and tag.has_attr("id"):
                if cur_issue.id != -1:
                    issue_list.append(cur_issue)
                cur_issue = Issue(tag["id"])
            else:
                if tag.name == "b" and tag.find("span") and tag.find("a"):
                    try:
                        cur_issue.issue_type = tag.find("span").text
                        cur_issue.issue_cve = tag.find("a").text
                        cur_issue.issue_cve_link = tag.find("a")["href"]
                    except AttributeError:
                        logger.error(f"Exception when parsing tag: {tag}")
                else:
                    cur_issue.trace += tag.text

    return issue_list
