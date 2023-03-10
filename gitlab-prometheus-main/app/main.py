from logging import Logger
import logging
from fastapi import FastAPI
from retro import run_retro2, get_group_issues, iteration_summarize_status,get_issue_counts
from retro import iteration_based_metrics,get_releases,run_team_issue_activity
#from titan import titan_wide
import requests
import os
import json
from starlette_exporter import PrometheusMiddleware, handle_metrics
from prometheus_client import Gauge, Info

logFormatter = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logFormatter, level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(PrometheusMiddleware)

@app.get("/")
async def read_root():
    return {"Hello": "World"}

### Gitlab Setup
project = {
    "GITLAB_URL":'https://gitlab.devops.sankhya.com.br/api/v4/',
    "GITLAB_PROJECT_ID": os.environ.get("CONFIG_PROJECT_ID"),
    "GITLAB_HEADERS": { 
            "PRIVATE-TOKEN": os.environ.get("GL_ACCESS_TOKEN") 
    },
    "CONFIG_FILE": os.environ.get("CONFIG_FILENAME"),
    "BRANCH_NAME": os.environ.get("CONFIG_BRANCH")
}

CONFIG_MAP = requests.get(
    project['GITLAB_URL'] + "projects/{}/repository/files/{}/raw?ref={}".format(project['GITLAB_PROJECT_ID'],project['CONFIG_FILE'],project['BRANCH_NAME']),
    headers=project['GITLAB_HEADERS'],
    verify=True
).json()
CONFIG_MAP.update(project)

groupName = CONFIG_MAP['team_label'].replace(" ","_")

ISSUE_WEIGHT = Gauge("gitlabkpis_Users_by_weight","Issue Weight by User",["group","iteration","team","user"])
ISSUE_STATUS = Gauge("gitlabkpis_Issues_by_status","Issue Counts by Status",["group","iteration","team","status"])
TIME_ESTIMATE = Gauge("gitlabkpis_time_estimate","Time Estimated by User",["group","iteration","team","user"])
TIME_SPENT = Gauge("gitlabkpis_time_spent","Time Spent by User",["group","iteration","team","user"])
TICKETS_USER = Gauge("gitlabkpis_tickets_by_user","Ticket Count by User",["group","iteration","team","user"])
TICKETS_CLOSED_USER = Gauge("gitlabkpis_tickets_closed_by_user","Ticket Closed by User (engineering complete)",["group","iteration","team","user"])
TICKETS_COMPLETE_USER = Gauge("gitlabkpis_tickets_completed_by_user","Ticket Closed by User (Dev GS::Done)",["group","iteration","team","user"])


BACKLOG_ISSUE_COUNT = Gauge("gitlabkpis_summary_issue_backlog_count","Number of issues in the Backlog",["group","team"])
ITERATION_ISSUE_COUNT = Gauge("gitlabkpis_summary_issue_count","Number of issues in the iteration",["group","iteration","team"])
ITERATION_WEIGHT = Gauge("gitlabkpis_summary_weight","Iteration issues weight",["group","iteration"])
ITERATION_LABEL_WEIGHT = Gauge("gitlabkpis_summary_label_weight","Iteration weight by label",["group","iteration","status"])
ITERATION_TIME_ESTIMATE = Gauge("gitlabkpis_summary_time_estimate","Time Estimated during Iteration",["group","iteration"])
ITERATION_TIME_SPENT = Gauge("gitlabkpis_summary_time_spent","Time Spent during iteration",["group","iteration"])
ITERATION_TIME_ESTIMATE_LABEL = Gauge("gitlabkpis_summary_time_estimate_by_status","Time Estimated during Iteration by label",["group","iteration","status"])
ITERATION_TIME_SPENT_LABEL = Gauge("gitlabkpis_summary_time_spent_by_status","Time Spent during iteration by label",["group","iteration","status"])
ITERATION_LABEL_CLASSIFICATION = Gauge("gitlabkpis_summary_issuegs_classification","Iteration weight by label",["group","iteration","team","status"])
ITERATION_COUNT_SEVERITY = Gauge("gitlabkpis_summary_count_severity","Ticket Count by Severity",["group","iteration","team","severity"])
ITERATION_COUNT_PRIORITY = Gauge("gitlabkpis_summary_count_priority","Ticket Count by Priority",["group","iteration","team","priority"])
ITERATION_MILESTONE_COUNT = Gauge("gitlabkpis_summary_count_milestone","Ticket Count by Milestone",["group","iteration","team","milestone"])
ITERATION_EPIC_COUNT = Gauge("gitlabkpis_summary_count_epic","Ticket Count by Epic",["group","iteration","team","epic"])
RELEASES_INFO = Info("gitlabkpis_summary_releases","Current Release and Release Counts")
VULN_SEV_INFO = Gauge("gitlabkpis_summary_vuln_severity","Vulnerability Counts by Severity",["group",'severity'])
VULN_SCANNER_INFO = Gauge("gitlabkpis_summary_vuln_scanner","Vulnerability Counts by Scanner",["group",'scanner'])
VULN_DETAILS_INFO = Gauge("gitlabkpis_summary_vuln_details","Vulnerability Counts by Scanner and Severity",["group",'scanner','severity'])
BUILD_STATUS_SUMMARY = Gauge("gitlabkpis_summary_build_status","Summary of Build status across all projects",["group",'status'])
BUILD_STATUS_PROJECTS = Gauge("gitlabkpis_project_build_status","Build status broken down by project",["group",'project','status'])



def build_metrics(request):

    ISSUE_WEIGHT.clear()
    ISSUE_STATUS.clear()
    TIME_ESTIMATE.clear()
    TIME_SPENT.clear()
    TICKETS_USER.clear()

    ITERATION_ISSUE_COUNT.clear()
    ITERATION_WEIGHT.clear()
    ITERATION_LABEL_WEIGHT.clear()
    ITERATION_TIME_ESTIMATE.clear()
    ITERATION_TIME_SPENT.clear()
    ITERATION_TIME_ESTIMATE_LABEL.clear()
    ITERATION_TIME_SPENT_LABEL.clear()
    ITERATION_LABEL_CLASSIFICATION.clear()
    ITERATION_COUNT_SEVERITY.clear()
    ITERATION_COUNT_PRIORITY.clear()
    ITERATION_MILESTONE_COUNT.clear()
    ITERATION_EPIC_COUNT.clear()
    TICKETS_CLOSED_USER.clear()
    TICKETS_COMPLETE_USER.clear()
    RELEASES_INFO.clear()
    BACKLOG_ISSUE_COUNT.clear()
    VULN_SEV_INFO.clear()
    VULN_SCANNER_INFO.clear()
    VULN_DETAILS_INFO.clear()
    BUILD_STATUS_SUMMARY.clear()
    BUILD_STATUS_PROJECTS.clear()

    logger.info("Getting Group Issues")
    (gl_issues,retroName) = get_group_issues(CONFIG_MAP)
    
    logger.info("Pulling Iteration Summary Status")
    (issue_summary_status,priority_tally,severity_tally) = iteration_summarize_status(gl_issues,CONFIG_MAP)
    for status in issue_summary_status:
        ISSUE_STATUS.labels(groupName,retroName,"coredev",status).set(issue_summary_status[status])
    
    for priority in priority_tally:
        ITERATION_COUNT_PRIORITY.labels(groupName,retroName,"coredev",priority).set(priority_tally[priority])
    for severity in severity_tally:
        ITERATION_COUNT_PRIORITY.labels(groupName,retroName,"coredev",severity).set(severity_tally[severity])

    # Issue count in Iteration
    ITERATION_ISSUE_COUNT.labels(groupName,retroName,"total").set(len(gl_issues))

    logger.info("Getting Issue Counts metric")
    (total_issues) = get_issue_counts(CONFIG_MAP,gl_issues)

    for team in CONFIG_MAP['teams']:
        ITERATION_ISSUE_COUNT.labels(groupName,retroName,team).set(total_issues[team]['iteration'])
        BACKLOG_ISSUE_COUNT.labels(groupName,team).set(total_issues[team]['backlog'])

    logger.info("Fetching Iteration based Metrics")
    (iteration_weight, label_weights,timeestimate,timespent,timesestimate_tally,timespent_tally,epic_tally_all,milestone_tally_all) = iteration_based_metrics(gl_issues,CONFIG_MAP)
    #Overall weight of the iteration
    ITERATION_WEIGHT.labels(groupName,retroName).set(iteration_weight)

    #Overall Time estimated in the iteration
    ITERATION_TIME_ESTIMATE.labels(groupName,retroName).set(timeestimate)

    #Overall time spend in the iteration
    ITERATION_TIME_SPENT.labels(groupName,retroName).set(timespent)

    # Time estimate by label 
    for status in timesestimate_tally:
        ITERATION_TIME_ESTIMATE_LABEL.labels(groupName,retroName, status).set(timesestimate_tally[status])
    
    #Time spent by label
    for status in timespent_tally:
        ITERATION_TIME_SPENT_LABEL.labels(groupName,retroName,status).set(timespent_tally[status])

    # Weight for a given label
    for label in label_weights:
        ITERATION_LABEL_WEIGHT.labels(groupName,retroName,label).set(label_weights[label])
    
    # Epic counts for Iteration
    for epic in epic_tally_all:
        ITERATION_EPIC_COUNT.labels(groupName,retroName,"coredev",epic).set(epic_tally_all[epic])
    # Milestone counts for Iteration
    for milestone in milestone_tally_all:
        ITERATION_MILESTONE_COUNT.labels(groupName,retroName,"coredev",milestone).set(milestone_tally_all[milestone])
    
    # Release Information
    if CONFIG_MAP['release_status'] == 1:
        logger.info("Getting Release Information")
        releases = get_releases(CONFIG_MAP)
        RELEASES_INFO.info({'version': releases['current'], 'release_date': releases['current_date'], 'short_date': releases['short_date'], "group": groupName})


    # Vuln Data
#    if CONFIG_MAP['vuln_status'] == 1 or CONFIG_MAP['pipeline_status']:
#        logger.info("Getting Vuln Information")
#        titan_wide_status = titan_wide(CONFIG_MAP)
#        for sev in titan_wide_status['vuln_sev']:
#            VULN_SEV_INFO.labels(groupName,sev).set(titan_wide_status['vuln_sev'][sev])
#        for scanner in titan_wide_status['vuln_scanner']:
#            VULN_SCANNER_INFO.labels(groupName,scanner).set(titan_wide_status['vuln_scanner'][scanner])
#        for scanner in titan_wide_status['vuln_details']:
#            for sev in titan_wide_status['vuln_details'][scanner]:
#                VULN_DETAILS_INFO.labels(groupName,scanner,sev).set(titan_wide_status['vuln_details'][scanner][sev])

    # Build Status
#    if CONFIG_MAP['pipeline_status'] == 1:
#        logger.info("Getting Build Status")
#        for status in titan_wide_status['pipeline_status']:
#            BUILD_STATUS_SUMMARY.labels(groupName,status).set(titan_wide_status['pipeline_status'][status])

    # Team based
    for team in CONFIG_MAP['teams']:
        logger.info("Fetching info for {}".format(team))
        (issue_weights_fe,time_spent_fe,time_estimate_fe,tickets_by_user_fe,issue_status_fe,label_class_fe,priority_fe,severity_fe,milestone_tally,epic_tally,user_closed_tally) = run_retro2(team,gl_issues,CONFIG_MAP)
        
        for status in tickets_by_user_fe:
            TICKETS_USER.labels(groupName,retroName,team,status).set(tickets_by_user_fe[status])
            
        for x in issue_status_fe:
            ISSUE_STATUS.labels(groupName,retroName,team,x).set(issue_status_fe[x])
        for y in issue_weights_fe:
            ISSUE_WEIGHT.labels(groupName,retroName,team,y).set(issue_weights_fe[y])
        for z in time_estimate_fe:
            TIME_ESTIMATE.labels(groupName,retroName,team,z).set(time_estimate_fe[z])
        for user in time_spent_fe:
            TIME_SPENT.labels(groupName,retroName,team,user).set(time_spent_fe[user])
        for status in label_class_fe:
            ITERATION_LABEL_CLASSIFICATION.labels(groupName,retroName,team,status).set(label_class_fe[status])
        for priority in priority_fe:
            ITERATION_COUNT_PRIORITY.labels(groupName,retroName,team,priority).set(priority_fe[priority])
        for severity in severity_fe:
            ITERATION_COUNT_PRIORITY.labels(groupName,retroName,team,severity).set(severity_fe[severity])
        for milestone in milestone_tally:
            ITERATION_MILESTONE_COUNT.labels(groupName,retroName,team,milestone).set(milestone_tally[milestone])
        for epic in epic_tally:
            ITERATION_EPIC_COUNT.labels(groupName,retroName,team,epic).set(epic_tally[epic])
        if CONFIG_MAP['issue_activity'] == 1:
            engDone = run_team_issue_activity(team,gl_issues,CONFIG_MAP)
            for user in engDone:
                TICKETS_CLOSED_USER.labels(groupName,retroName,team,user).set(engDone[user])
        for user in user_closed_tally:
            TICKETS_COMPLETE_USER.labels(groupName,retroName,team,user).set(user_closed_tally[user])
    logger.info("Finished Metrics")
    return handle_metrics(request)
    
app.add_route("/metrics", build_metrics)
