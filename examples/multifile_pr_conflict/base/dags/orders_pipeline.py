from airflow.operators.python import PythonOperator

publish = PythonOperator(task_id="publish_orders", output_field="order_total")
