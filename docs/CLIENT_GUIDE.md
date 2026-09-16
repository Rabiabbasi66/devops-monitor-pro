# DevOps Monitor Pro - Client Guide

This guide explains how to set up server monitoring with DevOps Monitor Pro in a few simple steps. No programming knowledge is required.

**What you need before you start:**

- A DevOps Monitor Pro dashboard account
- The Windows computer/server you want to monitor (Windows 10 or 11)
- An internet connection
- A Gmail (or other email) address to receive alert emails

---

## 1. Register / Log In

1. Open the DevOps Monitor Pro dashboard in your browser (the link you received with your account, or the dashboard linked from the project page).
2. New user? Click **Register**, enter a username, email and password.
3. Existing user? Enter your username and password and click **Log In**.

## 2. Add a Server

1. In the sidebar, open the **Servers** page.
2. Click **Add Server**.
3. Give the server a name (for example "Office File Server") and set your alert thresholds (CPU / memory / disk percentages that should trigger an alert).
4. Save. The server appears in your list with status **Unknown** until the agent connects.

## 3. Download the Windows Agent

1. With your server selected, click **Install Agent** (the wizard).
2. The wizard shows a **Download Windows Agent** button - download `DevOpsMonitorAgent-Setup.exe`.
3. Official download link (always the latest version):

```
https://github.com/Rabiabbasi66/devops-monitor-pro/releases/latest/download/DevOpsMonitorAgent-Setup.exe
```

## 4. Install the Agent

1. Copy the downloaded installer to the computer/server you want to monitor.
2. Right-click `DevOpsMonitorAgent-Setup.exe` and choose **Run as administrator**.
3. Follow the setup wizard and accept the installation.
4. Keep the wizard open - the next step needs a code from the dashboard.

## 5. Agent Enrollment / Connection

1. Back in the dashboard wizard, click **Generate Enrollment Code**. The code is valid for **20 minutes** and can be used **once**.
2. Paste the code into the installer's enrollment page and click **Next**.
3. The agent connects to the monitoring service automatically - no server IDs, tokens or configuration files needed.
4. Finish the installation. The agent starts monitoring immediately and restarts automatically after reboot.
5. On the dashboard, your server's status should change to **Online** within about a minute.

## 6. View Metrics

- Open the **Dashboard** page: every server shows a health icon (green/amber/red) plus live **CPU**, **Memory** and **Disk** bars.
- Click a server for detailed charts, history, and the top processes.
- **Alerts** shows triggered alerts; **Incidents** groups related alerts.
- Values refresh continuously - no manual refresh needed.

## 7. Configure Gmail

1. Open **Settings** in the sidebar.
2. Under **Email Notifications**, enter your Gmail address (for example `yourname@gmail.com`).
3. This address is where alert emails will be sent.

## 8. Verify Gmail with the Code

1. Click **Send verification code**.
2. Check your Gmail inbox for a message containing a **6-digit code** (valid for 10 minutes).
3. Type the code into the verification box and click **Verify Email**.
4. You will see "Email verified successfully" and can now save your preferences:
   - **Minimum severity**: info / warning / high / critical
   - **Notification types**: alerts, recovery, offline
   - **Cooldown**: minimum seconds between emails
5. Click **Test** to receive a real test email.

## 9. Receive Alert Emails

When a monitored value crosses your threshold (for example CPU above 95%), the platform:

1. Records an alert in the dashboard.
2. Sends an email to your verified Gmail address with the server name, the metric, the measured value, the threshold and the severity.
3. Sends a **recovery** email when the server returns to normal, and an **offline** email if the agent stops reporting.

## Troubleshooting

### Agent is not connecting

- **Enrollment code expired or already used** - codes are valid 20 minutes and single-use. Generate a new code in the Install Agent wizard and try again.
- **Check your internet** - the server you are installing on must be able to reach the internet.
- **Run as administrator** - the installer needs administrator rights.
- **Still failing?** - uninstall the agent, restart the computer, then install again with a fresh code.

### Server shows Offline

- The dashboard marks a server **Offline** when it has not received data for about 2 minutes.
- Check that the machine is powered on and connected to the internet.
- Check the **DevOps Monitor Agent** is running (Task Manager -> Services, or Task Scheduler task "DevOpsMonitorAgent").
- If you just rebooted, allow a minute for the agent to start.
- If the machine was offline for a long time, the first successful report automatically sends a **recovery** email and sets the status back to Online.

### Gmail verification code not received

- Wait 1-2 minutes and check again - email delivery can be delayed.
- Check the address you typed for typos, then request a **new code** (each code expires after 10 minutes).
- Look in the **Spam / Junk** folder.
- Make sure you are checking the same Gmail account you entered in Settings.

### Alert emails are going to Spam

- Open Gmail, find the email in Spam and click **Not spam** (or "Report not spam").
- Add the sender address to your Gmail **Contacts** so future emails are trusted.
- In Gmail settings you can also create a filter: "From: the platform sender -> Always mark as not spam".

### Dashboard is not showing metrics

- Allow up to a minute after installation for the first data to arrive.
- Refresh the browser page (F5) and select the correct server.
- Confirm the server card shows **Online** - if it is Offline, follow the "Server shows Offline" steps above.
- Confirm the platform is reachable: open `https://devops-monitor-pro.vercel.app/health` in a browser - it should say `status: healthy`.
- If the health page is not healthy, the monitoring service is temporarily down - try again shortly or contact support.

---

## Security Notes for Clients

- Your alert emails are sent by the platform - you never enter SMTP passwords anywhere.
- Enrollment codes are one-time and expire in 20 minutes.
- The agent stores its connection credentials securely on your machine (`C:\ProgramData\DevOpsMonitorPro\config.json`) and never displays them.
- Uninstalling the agent removes its credentials from your machine.

## Support

If problems continue, contact your account manager or the developer with:

1. The server name shown in the dashboard
2. What step of this guide you were on
3. A screenshot of the error or the dashboard status

2. Sends an email to your verified Gmail address with the server name, the metric, the measured value, the threshold and the severity.
3. Sends a **recovery** email when the server returns to normal, and an **offline** email if the agent stops reporting.
