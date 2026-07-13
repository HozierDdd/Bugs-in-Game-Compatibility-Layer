import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from utls.utls import chunk_loader, find_root_directory



class ReportDiscussionPairCollector:

    def __init__(self, sample_report_path: str, chunks_path: str):
        with open(sample_report_path, 'r', encoding='utf-8') as f:
            self.sample_report = json.load(f)
        self.issues = []
        self.chunks = chunk_loader(chunks_path=chunks_path)
        for chunk in self.chunks:
            for issue in chunk:
                self.issues.append(issue)
    

    def collect_following_discussions(self,
                                      all_comments,
                                      report_create_time: Optional[int] = 0
                                      ) -> List[Dict[str, Any]]:
        """
        Collect the following discussions for one specific compatibility report.
        Only comments created after report_create_time, excluding compatibility reports, max 50.
        Return:
            [
                "html_url": "https://github.com/ValveSoftware/Proton/issues/8363#issuecomment-2571388590",
                "body": "This appears to be a game issue, I could reproduce it on Windows 10 as well",
                "created_at": "2025-01-04T19:21:36Z",
                "is_for_the_report": null # true, false, not_sure
            ]
        """
        marker = "# Compatibility Report"
        comments = all_comments or []
        if report_create_time <= 0:
            print(f"ERROR: collect_following_discussions got invalid report_create_time={report_create_time}")
            return []
        eligible = []
        for c in comments:
            if marker in (c.get("body") or ""):
                continue
            created_at = c.get("created_at")
            if not created_at:
                print(f"ERROR: comment missing created_at (id={c.get('id')})")
                continue
            try:
                ts = int(datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                ).timestamp())
            except (ValueError, TypeError) as e:
                print(f"ERROR: failed to parse comment created_at={created_at!r}: {e}")
                continue
            if ts > report_create_time:
                eligible.append((ts, c))
        eligible = [c for _, c in sorted(eligible, key=lambda x: x[0])]
        out = []
        for c in eligible[:50]:
            out.append({
                "discussion_html_url": c.get("html_url", ""),
                "discussion_body": c.get("body") or "",
                "created_at": c.get("created_at"),
                "is_for_the_report": None,
            })
        return out

    def collect_report_discussion_pair(self):
        """
        Collect all compatibility reports and its following discussion pairs.
        Return:
            [
                {
                    "html_url": "https://github.com/ValveSoftware/Proton/issues/8363",
                    "issue_report_title": "vivid/stasis (2093940)",
                    "issue_number": 9198,
                    "state": "closed",
                    "body": "# Compatibility Report\r\n- Name of the game with compatibility issues: vivid/stasis\r\n- Steam AppID of the game: 2093940\r\n\r\n## System Information\r\n- GPU: NVIDIA GeForce GTX 1070/PCIe/SSE2\r\n- Video driver version: 4.6.0 NVIDIA 565.77\r\n- Kernel version: 6.12.7\r\n- Link to full system information report as [Gist](https://gist.github.com/nathannino/d9f05232f7d9f5372511447af468e369):\r\n- Proton version: experimental-9.0-20241223\r\n\r\n## I confirm:\r\n- [X] that I haven't found an existing compatibility report for this game.\r\n- [X] that I have checked whether there are updates for my system available.\r\n\r\n[steam-2093940.log](https://github.com/user-attachments/files/18283998/steam-2093940.log)\r\n<!-- Please add `PROTON_LOG=1 %command%` to the game's launch options and\r\nattach the generated $HOME/steam-$APPID.log to this issue report as a file.\r\n(Proton logs compress well if needed.)-->\r\n\r\n## Symptoms <!-- What's the problem? -->\r\nThe chart \"\\_\" will usually fail to load and crash the game. I have been able to reproduce it in boundary shatter, although someone else has mentioned it also crashing in the story [discord message](https://discord.com/channels/828252123154219028/954952378132611114/1323781995406561282), although after a while that person managed to somehow not crash once and as such could progress? [discord message](https://discord.com/channels/828252123154219028/954952378132611114/1323796923580420176) I don't have enough info on that, so I am only reporting what I can reproduce.\r\n\r\nThis does not seem to happen when playing on Windows\r\n\r\n## Reproduction\r\nAfter completing chapter 4, spam the tab button on the main menu until the boundary shatter menu option appears. Once in boundary shatter, scroll up or down until the cursor has the \"\\_\" chart selected. The moment it is selected, an exception will be thrown in the proton debug logs, and the game maker crash window will pop up.\r\n\r\nTo help with reproduction, this is part of my save file : [profile.txt](https://github.com/user-attachments/files/18284013/profile.txt)\r\nYou can place it at \"C:\\users\\steamuser\\AppData\\Local\\VIVIDSTASIS\" inside the proton prefix and name it \"profile\" without the .txt extension I added to make github allow me to upload the file. This should have \"\\_\" unlocked, and as such not require you to complete chapter 4. \r\n\r\nThis was last tested on the latest release of the game, which at the time of posting this report was version 4.0.2. I know that when the chart released (version 3.3.1), the chart could be selected and played. Additionally, version 3.4.0 and 3.4.1 do have a crash with \"\\_\" unrelated to proton, and as such unrelated to this report \r\n\r\n<!--\r\n1. You can find the Steam AppID in the URL of the shop page of the game.\r\n   e.g. for `The Witcher 3: Wild Hunt` the AppID is `292030`.\r\n2. You can find your driver and Linux version, as well as your graphics\r\n   processor's name in the system information report of Steam.\r\n3. You can retrieve a full system information report by clicking\r\n   `Help` > `System Information` in the Steam client on your machine.\r\n4. Please copy it to your clipboard by pressing `Ctrl+A` and then `Ctrl+C`.\r\n   Then paste it in a [Gist](https://gist.github.com/) and post the link in\r\n   this issue.\r\n5. Also, please copy the contents of `Help` > `Steam Runtime Diagnostics` to\r\n   the gist.\r\n6. Please search for open issues and pull requests by the name of the game and\r\n   find out whether they are relevant and should be referenced above.\r\n-->\r\n",
                    "created_at": "2025-01-01T00:21:55Z"
                    "following_discussion":
                        [
                            "html_url": "https://github.com/ValveSoftware/Proton/issues/8363#issuecomment-2571388590",
                            "body": "This appears to be a game issue, I could reproduce it on Windows 10 as well",
                            "created_at": "2025-01-04T19:21:36Z",
                                "is_for_the_report": null # true, false, not_sure
                        ]
                }
            ]
        """
        issue_by_number = {issue.get("number"): issue for issue in self.issues}
        result = []
        for item in self.sample_report:
            issue_number = item.get("issue_number")
            report_id = item.get("id")
            issue = issue_by_number.get(issue_number)
            if not issue:
                print(f"ERROR: issue_number={issue_number} not found in issues")
                continue
            comments_list = issue.get("comments_data") or []
            report_ts = 0
            html_url = None
            created_at = None
            body = item.get("compatibility_report") or ""

            if report_id == issue.get("id"):
                created_at = issue.get("created_at")
                html_url = issue.get("html_url")
                if not created_at:
                    print(f"ERROR: issue issue_number={issue_number} has no created_at")
                else:
                    try:
                        report_ts = int(datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        ).timestamp())
                    except (ValueError, TypeError) as e:
                        print(f"ERROR: failed to parse issue created_at={created_at!r} issue_number={issue_number}: {e}")
                if report_ts <= 0:
                    print(f"ERROR: invalid report_ts for issue body issue_number={issue_number}")
            else:
                for comment in comments_list:
                    if comment.get("id") == report_id:
                        created_at = comment.get("created_at")
                        html_url = comment.get("html_url") or (
                            (issue.get("html_url") or "") + "#issuecomment-" + str(report_id)
                        )
                        if not created_at:
                            print(f"ERROR: comment id={report_id} has no created_at")
                        else:
                            try:
                                report_ts = int(datetime.fromisoformat(
                                    created_at.replace("Z", "+00:00")
                                ).timestamp())
                            except (ValueError, TypeError) as e:
                                print(f"ERROR: failed to parse comment created_at={created_at!r} comment_id={report_id}: {e}")
                        if report_ts <= 0:
                            print(f"ERROR: invalid report_ts for comment id={report_id} issue_number={issue_number}")
                        break
                else:
                    print(f"ERROR: comment id={report_id} not found in issue_number={issue_number}")
                    continue

            following_discussion = self.collect_following_discussions(
                comments_list, report_create_time=report_ts
            )
            result.append({
                "issue_report_title": item.get("issue_title") or issue.get("title"),
                "issue_number": issue_number,
                "compatibility_report_html_url": html_url,
                "compatibility_report_id": report_id,
                "issue_state": issue.get("state"),
                "compatibility_report": body,
                "created_at": created_at,
                "following_discussion": following_discussion
            })
        return result

    def handle(self):
        result = self.collect_report_discussion_pair()
        root_dir = find_root_directory()
        out_path = root_dir / "data/compatibility_report_selection/report_discussion_pair.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    selector = ReportDiscussionPairCollector("data/compatibility_report_selection/random_sampling_report.json", "data/issue_filtered_selected")
    selector.handle()