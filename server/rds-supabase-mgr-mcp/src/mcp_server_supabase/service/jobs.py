"""Strict RDS single-job interpretation; never proves business completion."""

def job_result(payload, job_id):
    job = payload.get('job') if isinstance(payload, dict) else None
    state = 'unknown'
    if isinstance(job, dict) and job.get('id') == job_id:
        state = {'Running':'running','Completed':'completed','Failed':'failed'}.get(job.get('status'), 'unknown') if isinstance(job.get('status'),str) else 'unknown'
    # No arbitrary entities, free-form failure text, or resource secrets in tool output.
    return {'job_id':job_id, 'task_status':state,
            'data':{'job':{'id':job_id,'status':state}},
            'completion_verified':False, 'resource_verified':False, 'business_verified':False,
            'automatic_retry':False,
            'next_action': 'Verify expected resource state and business behavior; do not replay the write.' if state == 'completed'
                else 'Inspect the authorized task console and resource state; do not replay the write.' if state in ('failed','unknown')
                else 'Observe this same task again within an explicit observation budget.'}
