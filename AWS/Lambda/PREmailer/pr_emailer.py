# Some (well, honestly most) credit belongs to http://blog.rambabusaravanan.com/send-smtp-email-using-aws-lambda/

import json
import os
import smtplib
import requests
import github
import re
from email.message import EmailMessage

# Define some constants
CFE_COMMITS_ADDRESS = "cfe-commits@lists.llvm.org"
FLANG_COMMITS_ADDRESS = "flang-commits@lists.llvm.org"
LIBC_COMMITS_ADDRESS = "libc-commits@lists.llvm.org"
LIBCXX_COMMITS_ADDRESS = "libcxx-commits@lists.llvm.org"
LLD_COMMITS_ADDRESS = "llvm-commits@lists.llvm.org"
LLDB_COMMITS_ADDRESS = "lldb-commits@lists.llvm.org"
LLVM_BRANCH_COMMITS_ADDRESS = "llvm-branch-commits@lists.llvm.org"
LLVM_COMMITS_ADDRESS = "llvm-commits@lists.llvm.org"
OPENMP_COMMITS_ADDRESS = "openmp-commits@lists.llvm.org"
PARALLEL_LIBS_COMMITS_ADDRESS = "parallel_libs-commits@lists.llvm.org"
MLIR_COMMITS_ADDRESS = "mlir-commits@lists.llvm.org"


def create_project_list(file_list):
    # Iterate through each list to find the root path of each file.
    # Add the list of files to a set to get a uniquie list of project names.
    path_list = [i.split('/')[0].replace('.github', 'llvm') for i in file_list]
    path_temp_set = set(path_list)

    # Finally return a list of unique project names
    return list(set(list(path_temp_set)))


def format_diff(diff_url):
    # Get the diff from GitHub
    response = requests.get(diff_url)

    return response.text


def get_reply_to(diff_url):
    response = requests.get(diff_url)
    m = re.findall(r'From: (.+)', response.text)
    return m
    

# See: https://docs.python.org/3/library/email.examples.html#email-examples
def send_email(host, port, username, password, subject, body, mail_to, mail_from=None, reply_to=None):
    if mail_from is None: mail_from = username
    if reply_to is None: reply_to = mail_to

    try:
        email = EmailMessage()
        email.set_content(body)
        email['Subject'] = subject
        email['From'] = mail_from
        email['To'] = mail_to
        email['Reply-To'] = reply_to
        print(email)
        
        server = smtplib.SMTP(host, port)
        server.ehlo()
        server.starttls()
        server.login(username, password)
        server.send_message(email)
        server.close()
        return True
    except Exception as ex:
        print(ex)
        return False

def get_synchronize_email_body(event):

    user = event['sender']['login']
    pr_html = event['pull_request']['html_url']
    pr_number = event['pull_request']['number']
    diff = format_diff(event['pull_request']['patch_url'])
    return f"""
<a href='https://github.com/{user}'>{user}</a> updated <a href='{pr_html}'>PR#{pr_number}</a>:

{diff}
"""


def lambda_handler(event, context):
    # Define project path dict
    project_path_email = {
        'cfe-branch': LLVM_BRANCH_COMMITS_ADDRESS,
        'clang-tools-extra': CFE_COMMITS_ADDRESS,
        'clang': CFE_COMMITS_ADDRESS,
        'compiler-rt': LLVM_COMMITS_ADDRESS,
        'compiler-rt-tag': LLVM_BRANCH_COMMITS_ADDRESS,
        'debuginfo-tests': LLVM_COMMITS_ADDRESS,
        'flang': FLANG_COMMITS_ADDRESS,
        'libc': LIBC_COMMITS_ADDRESS,
        'libclc': CFE_COMMITS_ADDRESS,
        'libcxx': LIBCXX_COMMITS_ADDRESS,
        'libcxxabi': LIBCXX_COMMITS_ADDRESS,
        'libunwind': CFE_COMMITS_ADDRESS,
        'lld': LLD_COMMITS_ADDRESS,
        'lldb': LLDB_COMMITS_ADDRESS,
        'llvm': LLVM_COMMITS_ADDRESS,
        'mlir' : MLIR_COMMITS_ADDRESS,
        'openmp': OPENMP_COMMITS_ADDRESS,
        'parallel-libs': PARALLEL_LIBS_COMMITS_ADDRESS,
        'polly': LLVM_COMMITS_ADDRESS,
        'pstl': LIBCXX_COMMITS_ADDRESS,
        'zorg': LLVM_COMMITS_ADDRESS
    }
   
    gh_token = os.environ.get('GH_TOKEN')
    gh = github.Github(login_or_token=gh_token)
    pr_number = event['pull_request']['number']
    pr_title = event['pull_request']['title']
    user = gh.get_user(event['sender']['login'])
        
    host = os.environ.get('SMTPHOST')
    port = os.environ.get('SMTPPORT')
    mail_from = "{name}".format(name=user.name)
    origin = os.environ.get('ORIGIN')
    origin_req = ""
    password = os.environ.get('SMTP_PASSWORD')
    reply_to = ','.join(get_reply_to(event['pull_request']['patch_url']))
    username = os.environ.get('SMTP_USERNAME')

    action = event['action']
    body = ""

    if action == "synchronize":
        body = get_synchronize_email_body(event)

    # Get the project lists
    project_list = set()
    for commit in gh.get_repo('llvm/llvm-project').get_issue(pr_number).as_pull_request().get_commits():
        project_list.update(create_project_list([f.filename for f in commit.files]))
    # Track the email address last sent to
    last_mail_to = ""

    # Iterate through the list of projects and cross-post if necessary
    #print(project_list)
    #print(body)
    for project in project_list:
        # setup the MailTO
        # separate multiple recipient by comma. eg: "abc@gmail.com, xyz@gmail.com"
        # mail_to = os.environ['MAIL_TO']
        mail_to = project_path_email[project]

        if event['pull_request']['base']['ref'] != "main":
            mail_to = LLVM_BRANCH_COMMITS_ADDRESS

        # If we're sending an additional email to the same address, break instead
        if mail_to == last_mail_to:
            break

        mail_to = "tstellar@redhat.com"
        # Setup the mail Subject
        subject = f"[{project}] {pr_title} (PR #{pr_number})"

        # validate cors access
        cors = ''
        if not origin:
            cors = '*'
        elif origin_req in [o.strip() for o in origin.split(',')]:
            cors = origin_req

        # send mail
        success = False
        if cors:
            success = send_email(host, port, username, password, subject, body, mail_to, mail_from, reply_to)
            last_mail_to = mail_to
        else:
            print('mail_to: ', mail_to)
            print('mail_from: ', mail_from)
            print('reply_to: ', reply_to)
            print(subject)
            print(body)


    # prepare response
    response = {
        "isBase64Encoded": False,
        "headers": {"Access-Control-Allow-Origin": cors}
    }
    if success:
        response["statusCode"] = 200
        response["body"] = '{"status":true}'
    elif not cors:
        response["statusCode"] = 403
        response["body"] = '{"status":false}'
    else:
        response["statusCode"] = 400
        response["body"] = '{"status":false}'

    return {
        'statusCode': response["statusCode"],
        'body': response["body"]
    }




# Test

#synchronize_file = open('synchronize.json')
#synchronize_event = json.load(synchronize_file)

#lambda_handler(synchronize_event, None)
