#-------------------------------------------------------------------------------
import multiprocessing
import os
from os import path
import subprocess
import re
import time
import config
import database

#-------------------------------------------------------------------------------
remotehost = config.REMOTEHOST
remotehome = config.REMOTEHOME
pipe_launch = config.PIPE_LAUNCH

reJOBID = re.compile(r"Submitted batch job (?P<slurmid>\d+)")

#-------------------------------------------------------------------------------
def startJob( user, var1 ):
    jobid = database.createJob( user )

    p = multiprocessing.Process( target=runjob, args=(user, jobid, var1) )
    p.start()

#-------------------------------------------------------------------------------
def runjob( user, jobid, var1):
    print "RUNNING JOB " + str(jobid)

# stagein
    if hasattr(var1, "blat_custom_reads_n"):
        var1['BLAT_CUSTOM_READS'] = 'on'

    if hasattr(var1, "blat_custom_ass_n"):
        var1['BLAT_CUSTOM_ASS'] = 'on'

    if hasattr(var1, "file"):
        fileid1 = int(var1.file)
        localfile1 = database.getFileFullName( fileid1 )
        remotefile1 = os.path.join( remotehome, localfile1 )
        database.addJobFile( jobid, fileid1, database.FILEIN )
        var1['file_read1'] = remotefile1

    if hasattr(var1, "file2"):
        fileid2 = int(var1.file2)
        localfile2 = database.getFileFullName( fileid2 )
        remotefile2 = os.path.join( remotehome, localfile2 )
        database.addJobFile( jobid, fileid2, database.FILEIN )
        var1['file_read2'] = remotefile2

    if hasattr(var1, "file3"):
        fileid3 = int(var1.file3)
        localfile3 = database.getFileFullName( fileid3 )
        remotefile3 = os.path.join( remotehome, localfile3 )
        database.addJobFile( jobid, fileid3, database.FILEIN )
        var1['file_ass'] = remotefile3

        # submit
    if var1.input_type == "single":
        command = [ pipe_launch, user, str(var1), remotefile1, str(jobid) ]
    elif var1.input_type == "paired":
        command = [ pipe_launch, user, str(var1), remotefile1, remotefile2, str(jobid) ]
    elif var1.input_type =="contigs":
        command = [ pipe_launch, user, str(var1), remotefile3, str(jobid) ]
    elif var1.input_type =="contigs_with_single":
        command = [ pipe_launch, user, str(var1), remotefile1, remotefile3, str(jobid) ]
    elif var1.input_type =="contigs_with_paired":
        command = [ pipe_launch, user, str(var1), remotefile1, remotefile2, remotefile3, str(jobid) ]   

    print command

    for k in var1:
        print k + " : " + var1[k]

    proc = subprocess.Popen( command, stdout=subprocess.PIPE )
    output = proc.communicate()[0]
    mm = reJOBID.search( output )
    if mm:
        slurmid = int(mm.group('slurmid'))
        print "Slurm ID", str(slurmid)
        database.setJobSubmitted( jobid, slurmid )
    else:
        raise (-1)


#-------------------------------------------------------------------------------
def run():
    p = multiprocessing.Process( target=pipelineLoop )
    p.start()
    return p

#-------------------------------------------------------------------------------
def checkSlurmJob( slurmid ):
    command = ["ssh", remotehost, "mnq", "--job", str(slurmid) ]
    proc = subprocess.Popen( command, stdout=subprocess.PIPE )
    output = proc.communicate()[0]

    if len(output.splitlines()) <= 1:
        return database.JOB_COMPLETED

    mm = re.search( "RUNNING", output )
    if mm is not None:
        return database.JOB_RUNNING

    return database.JOB_SUBMITTED

#-------------------------------------------------------------------------------
def pipelineLoop():
    try:
        while (1 == 1):
            time.sleep( 100 )
            jobs = database.getActiveJobs()
            if len(jobs) > 0:
                print "Checking " + str(len(jobs)) + " job/s"

            for job in jobs:
                jobid = job['jid']
                newstate = checkSlurmJob( job['slurmid'] )
                if newstate == database.JOB_RUNNING and job['state'] != database.JOB_RUNNING:
                    database.setJobRunning( jobid )

                if newstate == database.JOB_COMPLETED:
                    userid = job['uid']
                    slurmid = job['slurmid']
                    # stageout
                    outs = ["jor_"+str(slurmid)+".out", "jor_"+str(slurmid)+".err"]
                    for fileoutname in outs:
                        fileout = database.createFile( userid, fileoutname )
                        database.addJobFile( jobid, fileout, database.FILEOUT )
                        localfile = database.getFileFullName( fileout )
                        (localdir, localbase) = os.path.split( localfile )
                        remotedir = os.path.join( remotehome, localdir )
                        remotefile = os.path.join( remotehome, localfile )
                        os.system('scp "%s:%s" "%s"' % (remotehost, remotefile, localfile) )

                    database.setJobCompleted( jobid )

    except KeyboardInterrupt:
        print "ending pipeline loop"

#-------------------------------------------------------------------------------
