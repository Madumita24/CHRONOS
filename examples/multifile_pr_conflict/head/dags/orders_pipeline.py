from airflow.operators.python import PythonOperator

# This file still declares the current identity.
publish = PythonOperator(task_id="publish_orders", output_field="order_total")
