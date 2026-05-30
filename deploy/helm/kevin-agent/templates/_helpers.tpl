{{/*
Expand the name of the chart.
*/}}
{{- define "kevin-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "kevin-agent.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "kevin-agent.labels" -}}
helm.sh/chart: {{ include "kevin-agent.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ include "kevin-agent.name" . }}
{{- end }}

{{/*
Backend labels
*/}}
{{- define "kevin-agent.backend.labels" -}}
{{ include "kevin-agent.labels" . }}
app.kubernetes.io/name: {{ include "kevin-agent.name" . }}-backend
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend labels
*/}}
{{- define "kevin-agent.frontend.labels" -}}
{{ include "kevin-agent.labels" . }}
app.kubernetes.io/name: {{ include "kevin-agent.name" . }}-frontend
app.kubernetes.io/component: frontend
{{- end }}
