UPDATE conpass_contractbody AS main
JOIN (
    SELECT contract_id, MAX(updated_at) AS max_updated_at
    FROM conpass_contractbody
    WHERE version IS NULL
    GROUP BY contract_id
) AS latest
ON main.contract_id = latest.contract_id AND main.updated_at = latest.max_updated_at
SET main.version = '1.0'
WHERE main.version IS NULL;

UPDATE conpass_contractbody SET status = 0 WHERE version is null;
