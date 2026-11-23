-- migration_003: view usada pelo relatório de ocupação (fica fora de db/migrations de propósito)
CREATE VIEW vw_ocupacao_diaria AS
SELECT medico_id, DATE(inicio) AS dia, COUNT(*) AS consultas
FROM consultas
WHERE status = 'agendada'
GROUP BY medico_id, DATE(inicio);
