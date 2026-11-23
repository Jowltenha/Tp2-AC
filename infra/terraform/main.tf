# Infraestrutura de produção do serviço de agendamento (responsabilidade da squad de plataforma)
resource "aws_db_instance" "agendamento" {
  identifier        = "agendamento-prod"
  engine            = "postgres"
  instance_class    = "db.t3.medium"
  allocated_storage = 50
}
